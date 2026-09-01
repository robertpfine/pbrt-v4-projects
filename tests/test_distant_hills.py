import json
import math
from copy import deepcopy
from pathlib import Path
import unittest

from distant_hills import (
    DistantHillLayer,
    create_distant_hill_grass,
    create_distant_hill_scatter,
    create_distant_hills,
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

    def test_enabled_module_builds_one_broad_rise(self):
        config = deepcopy(self.module_config)
        config["enabled"] = True
        layers = create_distant_hills(config)
        self.assertEqual(len(layers), 1)
        self.assertEqual(layers[0].name, "broad_rise")
        self.assertGreater(layers[0].depth, 1000.0)

    def test_explicit_peaks_define_silhouette_without_noise(self):
        config = dict(self.module_config["layers"][0])
        config["noise"] = dict(config["noise"], amplitude=0.0)
        layer = DistantHillLayer(config)
        primary = config["peaks"][0]
        peak_height = layer.ridge_height(primary["position"])
        valley_height = layer.ridge_height(0.98)
        self.assertGreater(peak_height, valley_height + 80.0)
        local_x = 0.5 * layer.width * primary["position"]
        ridge_z = layer.depth * (layer.ridge_position - 0.5)
        self.assertAlmostEqual(
            layer.height_local(local_x, ridge_z),
            layer.base_elevation + peak_height,
            places=7,
        )

    def test_band_has_concealed_edges_and_full_ridge(self):
        layer = DistantHillLayer(self.module_config["layers"][0])
        self.assertEqual(layer.cross_section(0.0), 0.0)
        self.assertAlmostEqual(layer.cross_section(layer.ridge_position), 1.0)
        self.assertEqual(layer.cross_section(1.0), 0.0)

    def test_mesh_is_deterministic_and_has_unit_normals(self):
        layer = DistantHillLayer(self.module_config["layers"][0])
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
        layer_config = deepcopy(self.module_config["layers"][0])
        layer_config["shading_normal_up_blend"] = 1.0
        _points, normals, _indices = DistantHillLayer(layer_config).mesh()
        self.assertTrue(all(normal == (0.0, 1.0, 0.0) for normal in normals))

    def test_horizon_vegetation_is_not_embedded_in_hills(self):
        self.assertNotIn("tree_line", self.module_config)

    def test_grass_extension_follows_hill_surface_deterministically(self):
        hill = DistantHillLayer(self.module_config["layers"][0])
        config = {
            "enabled": True,
            "count": 30,
            "seed": 19,
            "lateral_range": [-0.5, 0.5],
            "depth_range": [0.0, 0.62],
            "ridge_fade": {
                "enabled": True,
                "start": 0.44,
                "end": 0.56,
                "minimum_density": 0.0,
            },
            "scale": [0.5, 0.9],
            "variants": 3,
            "max_slope_degrees": 90.0,
            "y_offset": 0.05,
        }
        first = create_distant_hill_grass(hill, config)
        second = create_distant_hill_grass(hill, config)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 30)
        self.assertTrue(all(0 <= point.variant < 3 for point in first))
        self.assertTrue(all(0.5 <= point.scale <= 0.9 for point in first))

    def test_generic_detail_extension_uses_the_same_hill_surface_scatter(self):
        hill = DistantHillLayer(self.module_config["layers"][0])
        config = {
            "enabled": True,
            "count": 12,
            "seed": 23,
            "lateral_range": [-0.4, 0.4],
            "depth_range": [0.0, 0.5],
            "scale": [9.0, 26.0],
            "variants": 7,
            "max_slope_degrees": 90.0,
            "y_offset": 0.05,
        }
        points = create_distant_hill_scatter(hill, config)
        self.assertEqual(len(points), 12)
        self.assertTrue(all(0 <= point.variant < 7 for point in points))
        self.assertTrue(all(9.0 <= point.scale <= 26.0 for point in points))


if __name__ == "__main__":
    unittest.main()
