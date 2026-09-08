"""Basin geometry and validation without changing established terrain."""

from copy import deepcopy
import math
from pathlib import Path
import unittest

from scene_config import SceneConfig
from terrain import RollingHillside, create_terrain, validate_basin
from terrain_details import scatter_points, validate_elevation_range


class TerrainBasinTests(unittest.TestCase):
    def setUp(self):
        self.base = {"size": [800, 800], "resolution": [161, 161],
                     "base_height": 20, "noise": {"amplitude": 0}}
        self.basin = {"enabled": True, "center": [25, -30],
                      "radii": [200, 150], "floor_height": -40,
                      "inner_fraction": 0.5, "shore_variation": 0.12}

    def test_floor_shore_and_smooth_rim(self):
        terrain = RollingHillside({**self.base, "basin": self.basin})
        self.assertEqual(terrain.height(25, -30), -40)
        self.assertEqual(terrain.sample(25, -30).normal, (0, 1, 0))
        for i in range(48):
            angle = i * math.tau / 48
            x, z = math.cos(angle), math.sin(angle)
            self.assertEqual(terrain.height(25 + 80*x, -30 + 60*z), -40)
            self.assertEqual(terrain.height(25 + 230*x, -30 + 173*z), 20)
            # Cross the shoreline on every radial transect.
            self.assertLess(terrain.height(25 + 100*x, -30 + 75*z), 0)
            sample = terrain.sample(25 + 230*x, -30 + 173*z)
            self.assertAlmostEqual(sample.slope_degrees, 0)
        # At angle zero the harmonic rim is at normalized radius 1.048.
        rim_x = 25 + 200*1.048
        derivative = (terrain.height(rim_x + 0.01, -30)
                      - terrain.height(rim_x - 0.01, -30)) / 0.02
        self.assertAlmostEqual(derivative, 0, places=4)

    def test_disabled_is_identical_and_excavation_never_raises_low_ground(self):
        base = {**self.base, "noise": {"amplitude": 10, "seed": 37}}
        old = RollingHillside(base)
        disabled = RollingHillside({**base, "basin": {**self.basin, "enabled": False}})
        self.assertEqual(old.mesh(), disabled.mesh())
        lower = RollingHillside({**self.base, "base_height": -60, "basin": self.basin})
        self.assertEqual(lower.height(25, -30), -60)

    def test_invalid_controls_are_rejected(self):
        for field, value in (("radii", [0, 150]), ("radii", [1]),
                             ("center", [float("nan"), 0]),
                             ("floor_height", float("inf")),
                             ("inner_fraction", 1), ("inner_fraction", True),
                             ("shore_variation", 0.3), ("enabled", "yes")):
            with self.subTest(field=field, value=value):
                basin = {**self.basin, field: value}
                self.assertTrue(validate_basin(basin))
                with self.assertRaises(ValueError):
                    RollingHillside({**self.base, "basin": basin})
        self.assertTrue(validate_basin(None))

    def test_scene_validation_and_landform_world_coordinates(self):
        config = SceneConfig(Path(__file__).parent / "fixtures" / "canonical_config.json")
        landform = config.data["scene_description"]["landforms"][config.terrain_landform_index()]
        landform["topography"]["parameters"]["basin"] = deepcopy(self.basin)
        terrain = create_terrain(landform)
        self.assertLessEqual(terrain.height(25, -30), -40)
        self.assertFalse(config.validate())
        landform["topography"]["parameters"]["basin"]["radii"] = [-1, 150]
        self.assertTrue(any("basin.radii" in error for error in config.validate()))

    def test_low_shore_shelf_restores_hills_only_farther_back(self):
        basin = {**self.basin, "shore_variation": 0,
                 "shore": {"enabled": True, "height": 4, "width": 100, "transition": 200}}
        terrain = RollingHillside({**self.base, "basin": basin})
        self.assertEqual(terrain.height(25, -30), -40)
        # Radius 1 and 1.5: shelf. Radius 3.1: original terrain restored.
        self.assertEqual(terrain.height(225, -30), 4)
        self.assertEqual(terrain.height(325, -30), 4)
        self.assertEqual(terrain.height(645, -30), 20)
        self.assertGreater(terrain.height(425, -30), 4)
        self.assertLess(terrain.height(425, -30), 20)
        self.assertEqual(terrain.sample(235, -30).slope_degrees, 0)
        derivative = (terrain.height(225.01, -30) - terrain.height(224.99, -30)) / 0.02
        self.assertAlmostEqual(derivative, 0, places=4)

    def test_shore_validation_and_disabled_compatibility(self):
        for shore in (None, {"transition": 0}, {"width": -1},
                      {"height": float("nan")}, {"enabled": "yes"},
                      {"enabled": True, "height": -50}):
            with self.subTest(shore=shore):
                self.assertTrue(validate_basin({**self.basin, "shore": shore}))
        old = RollingHillside({**self.base, "basin": self.basin})
        disabled = RollingHillside({**self.base, "basin": {
            **self.basin, "shore": {"enabled": False, "height": 4}}})
        for x in range(-300, 301, 20):
            self.assertEqual(old.sample(x, -30), disabled.sample(x, -30))

    def test_rock_scatter_stays_in_waterline_elevation_band(self):
        terrain = RollingHillside({**self.base, "basin": self.basin})
        config = {"enabled": True, "count": 30, "seed": 81, "scale": [3, 8],
                  "region": {"center": [25, -30], "size": [450, 350]},
                  "elevation_range": [-3, 3], "y_offset": -1}
        first = scatter_points(terrain, config)
        self.assertEqual(first, scatter_points(terrain, config))
        self.assertEqual(len(first), 30)
        for point in first:
            x, y, z = point.position
            self.assertGreaterEqual(terrain.height(x, z), -3)
            self.assertLessEqual(terrain.height(x, z), 3)
            self.assertAlmostEqual(y, terrain.height(x, z) - 1)
        with self.assertRaisesRegex(ValueError, "elevation-constrained"):
            scatter_points(terrain, {**config, "elevation_range": [100, 101]})

    def test_scatter_interval_validation_reaches_scene_validator(self):
        for value in (None, [0], [2, 1], [0, float("inf")], [False, 1]):
            self.assertTrue(validate_elevation_range(value))
        config = SceneConfig(Path(__file__).parent / "fixtures" / "canonical_config.json")
        rock = next(o for l in config.data["scene_description"]["landforms"]
                    for o in l["surface_objects"] if o["generator"] == "rock_scatter")
        rock["population"]["elevation_range"] = [5, -5]
        self.assertTrue(any("population.elevation_range" in e for e in config.validate()))


if __name__ == "__main__":
    unittest.main()
