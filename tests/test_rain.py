import math
import unittest

from atmosphere import configured_rain
from rain import RainCurtain, create_rain_curtains


class RainCurtainTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "name": "test_shower",
            "center": [0.0, 2.0, -10.0],
            "size": [8.0, 4.0, 3.0],
            "resolution": [17, 11, 9],
        }
        self.module = {
            "enabled": True,
            "appearance": {"density": 1.0},
            "pattern": {
                "seed": 23,
                "coverage": 0.35,
                "softness": 0.25,
                "base_density": 0.45,
                "contrast": 0.55,
                "edge_fade_fraction": [0.15, 0.15, 0.20],
            },
        }

    def test_disabled_module_creates_no_curtains(self):
        self.assertEqual(create_rain_curtains({"enabled": False}), [])

    def test_density_grid_is_deterministic_and_nonempty(self):
        curtain = RainCurtain(self.config, self.module)
        first = curtain.density_grid()
        self.assertEqual(first, curtain.density_grid())
        self.assertEqual(len(first), math.prod(self.config["resolution"]))
        self.assertTrue(any(value > 0.0 for value in first))
        self.assertTrue(all(value >= 0.0 for value in first))

    def test_density_fades_to_zero_on_every_box_face(self):
        curtain = RainCurtain(self.config, self.module)
        x0, y0, z0 = curtain.bounds_min
        x1, y1, z1 = curtain.bounds_max
        xm, ym, zm = curtain.center
        for point in (
            (x0, ym, zm), (x1, ym, zm),
            (xm, y0, zm), (xm, y1, zm),
            (xm, ym, z0), (xm, ym, z1),
        ):
            self.assertEqual(curtain.density(*point), 0.0)

    def test_module_defaults_can_be_overridden_per_curtain(self):
        config = dict(self.config)
        config["appearance"] = {"density": 0.25}
        curtain = RainCurtain(config, self.module)
        self.assertEqual(curtain.optical["density_scale"], 0.25)

    def test_self_contained_rain_flattens_without_value_changes(self):
        description = {
            "atmosphere": {
                "rain": [{
                    "name": "test_shower",
                    "enabled": True,
                    "placement": {"position": self.config["center"]},
                    "dimensions": self.config["size"],
                    "density_field": {
                        "generator": "rain_curtain",
                        "resolution": self.config["resolution"],
                        **self.module["pattern"],
                    },
                    "medium": {
                        "type": "uniformgrid",
                        "density_scale": 1.0,
                        "scattering": [0.001, 0.002, 0.003],
                        "absorption": [0.0001, 0.0002, 0.0003],
                        "anisotropy": 0.35,
                    },
                }]
            }
        }
        normalized = configured_rain(description)
        curtain = normalized["curtains"][0]
        self.assertTrue(normalized["enabled"])
        self.assertEqual(curtain["center"], self.config["center"])
        self.assertEqual(curtain["size"], self.config["size"])
        self.assertEqual(curtain["resolution"], self.config["resolution"])
        self.assertEqual(curtain["pattern"], self.module["pattern"])
        self.assertEqual(curtain["appearance"]["density"], 1.0)


if __name__ == "__main__":
    unittest.main()
