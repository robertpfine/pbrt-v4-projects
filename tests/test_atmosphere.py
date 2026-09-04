import re
import unittest
from types import SimpleNamespace

from atmosphere import configured_fog

try:
    from scene_workspace.build_scene import write_cloud_boundaries, write_fog_medium
except ModuleNotFoundError:
    write_cloud_boundaries = None
    write_fog_medium = None


@unittest.skipIf(write_fog_medium is None, "atmosphere builder requires NumPy")
class FogHeightFalloffTests(unittest.TestCase):
    def fog_config(self):
        return {
            "scene_description": {
                "atmosphere": {
                    "fog": [{
                        "name": "test_fog",
                        "enabled": True,
                        "boundary": {
                            "active_shape": "sphere",
                            "camera_inside": True,
                            "sphere": {
                                "center": [0.0, 0.0, 0.0],
                                "radius": 10.0,
                            },
                        },
                        "density_field": {
                            "generator": "perlin",
                            "enabled": True,
                            "resolution": [2, 3, 2],
                            "bounds_min": [0.0, 0.0, 0.0],
                            "bounds_max": [1.0, 10.0, 1.0],
                            "frequency": 0.01,
                            "octaves": 1,
                            "persistence": 0.5,
                            "lacunarity": 2.0,
                            "base_density": 1.0,
                            "contrast": 0.0,
                            "height_falloff": {
                                "enabled": True,
                                "full_density_height": 0.0,
                                "zero_density_height": 10.0,
                                "exponent": 1.0,
                            },
                        },
                        "medium": {
                            "name": "fog",
                            "type": "uniformgrid",
                            "absorption": 0.0,
                            "scattering": 0.001,
                            "anisotropy": 0.0,
                        },
                    }],
                }
            }
        }

    def test_height_falloff_reaches_zero_smoothly(self):
        lines = []
        write_fog_medium(self.fog_config(), lines)
        text = "\n".join(lines)
        block = re.search(r'"float density" \[\n(.*?)\n    \]', text, re.S)
        self.assertIsNotNone(block)
        density = [float(value) for value in block.group(1).split()]
        self.assertEqual(density[0:2], [1.0, 1.0])
        self.assertEqual(density[2:4], [0.5, 0.5])
        self.assertEqual(density[4:6], [0.0, 0.0])

    def test_self_contained_fog_flattens_without_value_changes(self):
        fog = configured_fog(self.fog_config()["scene_description"])
        self.assertEqual(fog["sigma_a"], 0.0)
        self.assertEqual(fog["sigma_s"], 0.001)
        self.assertEqual(fog["g"], 0.0)
        self.assertEqual(fog["boundary_center"], [0.0, 0.0, 0.0])
        self.assertEqual(fog["boundary_radius"], 10.0)
        self.assertEqual(fog["noise"]["type"], "perlin")

    def test_invalid_height_range_is_rejected(self):
        config = self.fog_config()
        config["scene_description"]["atmosphere"]["fog"][0]["density_field"]["height_falloff"][
            "zero_density_height"
        ] = 0.0
        with self.assertRaisesRegex(ValueError, "zero_density_height"):
            write_fog_medium(config, [])

    def test_cloud_boundary_can_return_to_surrounding_fog(self):
        formation = SimpleNamespace(
            name="test_cloud",
            bounds_min=(0.0, 1.0, 2.0),
            bounds_max=(3.0, 4.0, 5.0),
        )
        lines = []
        write_cloud_boundaries(lines, [formation], exterior_medium="fog")
        self.assertIn(
            '    MediumInterface "cloud_0_test_cloud" "fog"',
            lines,
        )


if __name__ == "__main__":
    unittest.main()
