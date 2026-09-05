import math
import unittest

from clouds import CloudFormation, configured_cloud_module, create_clouds


class CloudFormationTests(unittest.TestCase):
    def test_self_contained_cloud_adapter_preserves_explicit_values(self):
        sky = {
            "cloud_grid_builder": {"backend": "python"},
            "clouds": [{
                "name": "deck",
                "enabled": True,
                "placement": {"position": [1, 2, 3]},
                "dimensions": [4, 5, 6],
                "boundary": {"mode": "axis_aligned"},
                "density_field": {
                    "generator": "mottled_veil",
                    "resolution": [7, 8, 9],
                    "shape": {"bottom_fade": 1},
                    "noise": {"seed": 12},
                    "depth_slope": {"enabled": False},
                    "depth_profile": {"enabled": False},
                    "lobes": [],
                },
                "medium": {
                    "type": "uniformgrid",
                    "density_scale": 0.9,
                    "scattering": [0.1, 0.2, 0.3],
                    "absorption": [0.01, 0.02, 0.03],
                    "anisotropy": 0.4,
                    "underside": {"enabled": False},
                },
            }],
        }
        module = configured_cloud_module(sky)
        formation = module["formations"][0]
        self.assertEqual(module["grid_builder"], {"backend": "python"})
        self.assertEqual(formation["center"], [1, 2, 3])
        self.assertEqual(formation["form"], "mottled_veil")
        self.assertEqual(formation["appearance"]["density"], 0.9)
        self.assertEqual(formation["boundary"], {"mode": "axis_aligned"})

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

    def test_formation_can_override_shared_cloud_controls(self):
        config = dict(self.config)
        config["appearance"] = {
            "density": 0.25,
            "underside": {"enabled": False},
        }
        config["fractal_noise"] = {"coverage": 0.72}
        cloud = CloudFormation(config, self.module_config)
        self.assertEqual(cloud.optical["density_scale"], 0.25)
        self.assertFalse(cloud.underside["enabled"])
        self.assertEqual(cloud.fractal_noise["coverage"], 0.72)
        self.assertEqual(
            cloud.fractal_noise["frequency"],
            self.module_config["fractal_noise"]["frequency"],
        )

    def test_depth_profile_retains_near_density_and_reduces_far_density(self):
        config = dict(self.config)
        config["depth_profile"] = {
            "enabled": True,
            "full_density_until_z": -10.0,
            "falloff_distance": 10.0,
            "far_density_scale": 0.04,
        }
        cloud = CloudFormation(config, self.module_config)
        self.assertEqual(cloud._depth_profile_weight(0.0), 1.0)
        self.assertEqual(cloud._depth_profile_weight(-10.0), 1.0)
        self.assertAlmostEqual(
            cloud._depth_profile_weight(-20.0), math.exp(-1.0)
        )
        self.assertAlmostEqual(cloud._depth_profile_weight(-50.0), 0.04)
        self.assertAlmostEqual(cloud._depth_profile_weight(-80.0), 0.04)

    def test_depth_slope_lowers_only_the_far_end_of_the_deck(self):
        config = dict(self.config)
        config["center"] = [0.0, 10.0, -10.0]
        config["size"] = [10.0, 4.0, 20.0]
        config["depth_slope"] = {
            "enabled": True,
            "far_y_offset": -3.0,
        }
        cloud = CloudFormation(config, self.module_config)
        self.assertEqual(cloud.base_bounds_min, (-5.0, 8.0, -20.0))
        self.assertEqual(cloud.base_bounds_max, (5.0, 12.0, 0.0))
        self.assertEqual(cloud.bounds_min, (-5.0, 5.0, -20.0))
        self.assertEqual(cloud.bounds_max, (5.0, 12.0, 0.0))
        self.assertEqual(cloud._depth_slope_offset(0.0), 0.0)
        self.assertEqual(cloud._depth_slope_offset(-10.0), -1.5)
        self.assertEqual(cloud._depth_slope_offset(-20.0), -3.0)
        near_optical = cloud.optical_coefficients(0.5, 9.0, 0.0)
        far_optical = cloud.optical_coefficients(0.5, 6.0, -20.0)
        self.assertEqual(near_optical, far_optical)

    def corner_veil(self, fades=None):
        config = {
            "name": "corner_deck",
            "form": "mottled_veil",
            "center": [0.0, 5.0, 0.0],
            "size": [20.0, 4.0, 20.0],
            "resolution": [7, 5, 7],
            "boundary": {
                "mode": "corner_prism",
                "bottom_corners": {
                    "near_left": [-10.0, 10.0, 10.0],
                    "near_right": [10.0, 10.0, 10.0],
                    "far_right": [10.0, 0.0, -10.0],
                    "far_left": [-10.0, 0.0, -10.0],
                },
                "thickness": 4.0,
            },
        }
        module = {
            "appearance": {"density": 1.0},
            "fractal_noise": {
                "frequency": [0.0, 0.0, 0.0],
                "coverage": -1.0,
                "softness": 0.1,
                "edge_fade_fraction": fades or {
                    "left": 0.0, "right": 0.0,
                    "bottom": 0.0, "top": 0.0,
                    "near": 0.0, "far": 0.0,
                },
            },
        }
        return CloudFormation(config, module)

    def test_corner_prism_derives_watertight_vertices_and_density_support(self):
        cloud = self.corner_veil()
        self.assertEqual(cloud.bounds_min, (-10.0, 0.0, -10.0))
        self.assertEqual(cloud.bounds_max, (10.0, 14.0, 10.0))
        self.assertEqual(cloud.boundary.bottom_y(0.0, 0.0), 5.0)
        self.assertTrue(cloud.boundary.contains((0.0, 7.0, 0.0)))
        self.assertFalse(cloud.boundary.contains((0.0, 4.0, 0.0)))
        self.assertGreater(cloud.density(0.0, 7.0, 0.0), 0.9)
        self.assertEqual(cloud.density(20.0, 7.0, 0.0), 0.0)
        self.assertEqual(
            cloud.boundary.vertices()[0:4],
            ((-10.0, 0.0, -10.0), (10.0, 0.0, -10.0),
             (10.0, 4.0, -10.0), (-10.0, 4.0, -10.0)),
        )

    def test_corner_prism_supports_independent_near_face_fade(self):
        fades = {
            "left": 0.0, "right": 0.0,
            "bottom": 0.0, "top": 0.0,
            "near": 0.5, "far": 0.0,
        }
        cloud = self.corner_veil(fades)
        near = cloud.density(0.0, 11.5, 9.0)
        middle = cloud.density(0.0, 7.0, 0.0)
        self.assertGreater(middle, near)
        self.assertGreater(near, 0.0)

    def test_corner_prism_rejects_twisted_bottom_and_depth_slope(self):
        cloud = self.corner_veil()
        source = {
            "name": "bad",
            "form": "mottled_veil",
            "center": [0, 0, 0],
            "size": [2, 2, 2],
            "boundary": cloud.boundary.contract(),
        }
        source["boundary"]["bottom_corners"]["far_left"][1] += 1.0
        with self.assertRaisesRegex(ValueError, "coplanar"):
            CloudFormation(source)
        source["boundary"] = cloud.boundary.contract()
        source["depth_slope"] = {"enabled": True, "far_y_offset": -1.0}
        with self.assertRaisesRegex(ValueError, "depth_slope must be disabled"):
            CloudFormation(source)

    def test_equivalent_corner_prism_preserves_legacy_slope_density(self):
        module = {
            "appearance": {"density": 0.9},
            "fractal_noise": {
                "seed": 823,
                "frequency": [0.045, 0.12, 0.055],
                "octaves": 2,
                "coverage": 0.34,
                "softness": 0.32,
                "edge_fade_fraction": [0.08, 0.15, 0.1],
            },
        }
        legacy = {
            "name": "legacy_slope",
            "form": "mottled_veil",
            "center": [0.0, 10.0, -10.0],
            "size": [20.0, 4.0, 20.0],
            "resolution": [7, 6, 8],
            "depth_slope": {"enabled": True, "far_y_offset": -3.0},
        }
        explicit = {
            **legacy,
            "name": "explicit_prism",
            "depth_slope": {"enabled": False, "far_y_offset": -3.0},
            "boundary": {
                "mode": "corner_prism",
                "bottom_corners": {
                    "near_left": [-10.0, 8.0, 0.0],
                    "near_right": [10.0, 8.0, 0.0],
                    "far_right": [10.0, 5.0, -20.0],
                    "far_left": [-10.0, 5.0, -20.0],
                },
                "thickness": 4.0,
            },
        }
        legacy_density = CloudFormation(legacy, module).density_grid()
        explicit_density = CloudFormation(explicit, module).density_grid()
        self.assertLessEqual(
            max(abs(left - right) for left, right in zip(
                legacy_density, explicit_density
            )),
            1e-12,
        )

if __name__ == "__main__":
    unittest.main()
