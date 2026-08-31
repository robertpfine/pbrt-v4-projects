import json
import math
from copy import deepcopy
from pathlib import Path
import unittest

from distant_hills import (
    DistantHillLayer,
    create_distant_hills,
    create_horizon_tree_line,
)


class DistantHillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.module_config = json.loads(
            (root / "scene_workspace" / "config.json").read_text(encoding="utf-8")
        )["scene"]["landscape"]["distant_hills"]

    def test_disabled_module_creates_no_geometry(self):
        config = dict(self.module_config)
        config["enabled"] = False
        self.assertEqual(create_distant_hills(config), [])

    def test_enabled_module_builds_all_differentiated_layers(self):
        config = deepcopy(self.module_config)
        config["enabled"] = True
        for layer in config["layers"]:
            layer["enabled"] = True
        layers = create_distant_hills(config)
        expected_names = [layer["name"] for layer in config["layers"]]
        self.assertEqual([layer.name for layer in layers], expected_names)
        self.assertEqual(len({layer.width for layer in layers}), len(layers))
        self.assertEqual(
            len({layer.ridge_base_height for layer in layers}),
            len(layers),
        )
        self.assertEqual(len({layer.reflectance for layer in layers}), len(layers))

    def test_explicit_peaks_define_silhouette_without_noise(self):
        config = dict(self.module_config["layers"][0])
        config["noise"] = dict(config["noise"], amplitude=0.0)
        layer = DistantHillLayer(config)
        primary = config["peaks"][1]
        peak_height = layer.ridge_height(primary["position"])
        valley_height = layer.ridge_height(0.98)
        self.assertGreater(peak_height, valley_height + 25.0)
        local_x = 0.5 * layer.width * primary["position"]
        ridge_z = layer.depth * (layer.ridge_position - 0.5)
        self.assertAlmostEqual(
            layer.height_local(local_x, ridge_z),
            layer.base_elevation + peak_height,
            places=7,
        )

    def test_authored_ridge_profile_preserves_summits_and_valleys(self):
        config = deepcopy(self.module_config["layers"][-1])
        config["noise"] = dict(config["noise"], amplitude=0.0)
        layer = DistantHillLayer(config)
        profile = config["ridge_profile"]
        for control in profile:
            self.assertAlmostEqual(
                layer.ridge_height(control["position"]),
                control["height"],
            )
        authored_heights = [control["height"] for control in profile]
        self.assertGreater(
            max(authored_heights),
            min(authored_heights) + 50.0,
        )

    def test_band_has_concealed_edges_and_full_ridge(self):
        layer = DistantHillLayer(self.module_config["layers"][1])
        self.assertEqual(layer.cross_section(0.0), 0.0)
        self.assertAlmostEqual(layer.cross_section(layer.ridge_position), 1.0)
        self.assertEqual(layer.cross_section(1.0), 0.0)

    def test_mesh_is_deterministic_and_has_unit_normals(self):
        layer = DistantHillLayer(self.module_config["layers"][2])
        first = layer.mesh()
        second = layer.mesh()
        self.assertEqual(first, second)
        points, normals, indices = first
        self.assertEqual(len(points), layer.nx * layer.nz)
        self.assertEqual(len(indices), (layer.nx - 1) * (layer.nz - 1) * 6)
        for normal in normals[:: max(1, len(normals) // 20)]:
            self.assertAlmostEqual(
                math.sqrt(sum(value * value for value in normal)), 1.0, places=7
            )

    def test_atmospheric_normal_blend_softens_far_range_shading(self):
        layer_config = deepcopy(self.module_config["layers"][-1])
        layer_config["shading_normal_up_blend"] = 1.0
        _points, normals, _indices = DistantHillLayer(layer_config).mesh()
        self.assertTrue(all(normal == (0.0, 1.0, 0.0) for normal in normals))

    def test_horizon_tree_line_is_sparse_deterministic_and_ridge_anchored(self):
        config = deepcopy(self.module_config)
        config["tree_line"]["enabled"] = True
        hills = create_distant_hills(config)
        first = create_horizon_tree_line(config, hills)
        second = create_horizon_tree_line(config, hills)
        self.assertEqual(first, second)
        self.assertEqual(len(first), config["tree_line"]["count"])
        height_min, height_max = config["tree_line"]["height"]
        radius_min, radius_max = config["tree_line"]["crown_radius"]
        self.assertTrue(all(
            height_min <= tree.height <= height_max
            and radius_min <= tree.crown_radius <= radius_max
            for tree in first if tree.form == "deciduous"
        ))
        self.assertEqual({tree.form for tree in first}, {"deciduous", "evergreen"})
        evergreen_height = config["tree_line"]["evergreen_height"]
        evergreen_radius = config["tree_line"]["evergreen_crown_radius"]
        self.assertTrue(all(
            evergreen_height[0] <= tree.height <= evergreen_height[1]
            and evergreen_radius[0] <= tree.crown_radius <= evergreen_radius[1]
            for tree in first if tree.form == "evergreen"
        ))

    def test_disabled_horizon_tree_line_creates_no_instances(self):
        config = deepcopy(self.module_config)
        config["tree_line"]["enabled"] = False
        self.assertEqual(create_horizon_tree_line(config), [])


if __name__ == "__main__":
    unittest.main()
