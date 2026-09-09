from pathlib import Path
import unittest

from scene_config import SceneConfig
from stone_texture import validate_stone_texture, write_granite_surface


class StoneTextureTests(unittest.TestCase):
    def test_invalid_surface_controls_are_rejected(self):
        for config in (None, {"generator": "unknown"}, {"grain_size": 0},
                       {"mottle_size": float("nan")}, {"grain_strength": 1.1},
                       {"bump_height": -1}, {"enabled": "true"},
                       {"grain_dark": [0, 0, 10.13]}, {"grain_light": [1, 1]}):
            with self.subTest(config=config):
                self.assertTrue(validate_stone_texture(config))
                with self.assertRaises(ValueError):
                    write_granite_surface([], "test", config, [0.1]*3)

    def test_material_has_bounded_color_mixes_and_separate_bump(self):
        lines = []
        write_granite_surface(lines, "rock", {"grain_size": 0.8, "bump_height": 0.2}, [0.1]*3)
        text = '\n'.join(lines)
        self.assertIn('Scale 0.8 0.8 0.8', text)
        self.assertIn('"texture displacement" [ "rock_bump" ]', text)
        self.assertIn('"texture reflectance" [ "rock_color" ]', text)
        # Noise bound +/-2, four octave weights 1, .5, .25, .125.
        self.assertGreaterEqual(0.5 - 0.125*2*1.875, 0)
        self.assertLessEqual(0.5 + 0.125*2*1.875, 1)
        self.assertEqual(text.count('AttributeBegin'), text.count('AttributeEnd'))

    def test_scene_validator_checks_rock_texture_and_grass_margin(self):
        config = SceneConfig(Path(__file__).parent / 'fixtures' / 'canonical_config.json')
        objects = [o for l in config.data['scene_description']['landforms'] for o in l['surface_objects']]
        rock = next(o for o in objects if o['generator'] == 'rock_scatter')
        rock['construction']['texture'] = {'enabled': True, 'grain_light': [0, 0, 1.5]}
        grass = next(o for o in objects if o['generator'] == 'grass')
        grass['population']['camera_frustum']['side_margin'] = -0.2
        errors = config.validate()
        self.assertTrue(any('texture.grain_light' in e for e in errors))
        self.assertTrue(any('side_margin' in e for e in errors))
