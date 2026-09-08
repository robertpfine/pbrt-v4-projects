"""Basin geometry and validation without changing established terrain."""

from copy import deepcopy
import math
from pathlib import Path
import unittest

from scene_config import SceneConfig
from terrain import RollingHillside, create_terrain, validate_basin


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


if __name__ == "__main__":
    unittest.main()
