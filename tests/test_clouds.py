import math
import unittest

from clouds import CloudFormation, create_clouds


class CloudFormationTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "name": "test_cloud",
            "enabled": True,
            "center": [0.0, 0.5, 0.0],
            "size": [4.0, 3.0, 4.0],
            "resolution": [7, 6, 7],
            "lobes": [
                {"center_offset": [0.0, -0.2, 0.0], "radii": [1.6, 0.9, 1.4]},
                {"center_offset": [0.5, 0.5, 0.0], "radii": [0.7, 0.9, 0.7]},
            ],
        }
        self.module_config = {
            "shape": {"bottom_fade": 0.3, "top_fade": 0.3},
            "fractal_noise": {
                "seed": 11,
                "frequency": 0.4,
                "octaves": 2,
                "roughness": 0.5,
                "frequency_jump": 2.0,
                "coverage": 0.10,
                "softness": 0.22,
                "edge_influence": 0.28,
                "density_contrast": 0.65,
                "domain_warp": {
                    "enabled": True,
                    "frequency": 0.25,
                    "strength": [0.35, 0.20, 0.35],
                },
            },
            "appearance": {
                "density": 1.0,
                "scattering": [0.006, 0.007, 0.008],
                "absorption": [0.001, 0.001, 0.001],
                "underside": {
                    "enabled": True,
                    "height_fraction": 0.42,
                    "transition": 0.20,
                    "scattering_scale": 0.40,
                    "absorption_scale": 4.0,
                },
            },
        }

    def test_disabled_module_creates_no_clouds(self):
        self.assertEqual(create_clouds({"enabled": False}), [])

    def test_density_grid_is_bounded_deterministic_and_nonempty(self):
        cloud = CloudFormation(self.config, self.module_config)
        first = cloud.density_grid()
        second = cloud.density_grid()
        self.assertEqual(first, second)
        self.assertEqual(len(first), math.prod(self.config["resolution"]))
        self.assertTrue(any(value > 0.0 for value in first))
        self.assertTrue(all(0.0 <= value <= 1.0 for value in first))

    def test_density_fades_to_zero_at_vertical_bounds(self):
        cloud = CloudFormation(self.config, self.module_config)
        self.assertEqual(cloud.density(0.0, -1.0, 0.0), 0.0)
        self.assertEqual(cloud.density(0.0, 2.0, 0.0), 0.0)

    def test_fractal_density_does_not_excavate_the_cloud_core(self):
        cloud = CloudFormation(self.config, self.module_config)
        self.assertGreater(cloud.density(0.0, 0.3, 0.0), 0.25)

    def test_underside_absorbs_more_and_scatters_less(self):
        cloud = CloudFormation(self.config, self.module_config)
        bottom_a, bottom_s = cloud.optical_coefficients(1.0, -0.8)
        top_a, top_s = cloud.optical_coefficients(1.0, 1.8)
        self.assertGreater(bottom_a[0], top_a[0])
        self.assertLess(bottom_s[0], top_s[0])
        sigma_a_grid, sigma_s_grid = cloud.optical_grids()
        expected = 3 * math.prod(self.config["resolution"])
        self.assertEqual(len(sigma_a_grid), expected)
        self.assertEqual(len(sigma_s_grid), expected)

    def test_mottled_veil_needs_no_lobes_and_spans_a_volume(self):
        veil_config = {
            "name": "test_veil",
            "form": "mottled_veil",
            "center": [0.0, 2.0, -10.0],
            "size": [12.0, 6.0, 2.0],
            "resolution": [12, 8, 5],
        }
        veil_module = {
            "appearance": {"density": 0.6},
            "fractal_noise": {
                "seed": 9,
                "frequency": [0.12, 0.25, 0.4],
                "octaves": 2,
                "roughness": 0.5,
                "frequency_jump": 2.0,
                "coverage": 0.48,
                "softness": 0.30,
                "edge_fade_fraction": [0.1, 0.1, 0.2],
            },
        }
        veil = CloudFormation(veil_config, veil_module)
        density = veil.density_grid()
        self.assertEqual(len(density), math.prod(veil_config["resolution"]))
        self.assertTrue(any(value > 0.0 for value in density))
        self.assertEqual(density, veil.density_grid())


if __name__ == "__main__":
    unittest.main()
