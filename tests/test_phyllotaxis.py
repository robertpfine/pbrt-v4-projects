import math
import unittest

from phyllotaxis import dome_height, vogel_points
from scene_workspace.build_scene import configured_scene_objects


class VogelPointTests(unittest.TestCase):
    def test_independent_object_adapter_preserves_generator_inputs(self):
        description = {
            "objects": [
                {
                    "name": "sunflower",
                    "enabled": False,
                    "placement": {
                        "position": [1.0, 2.0, 3.0],
                        "rotation_degrees": [4.0, 5.0, 6.0],
                    },
                    "geometry": {"generator": "planar_phyllotaxis"},
                    "material": {},
                    "construction": {"count": 630, "spacing": 1.3},
                }
            ]
        }

        self.assertEqual(
            configured_scene_objects(description, "planar_phyllotaxis"),
            [
                {
                    "enabled": False,
                    "label": "sunflower",
                    "_placement": {
                        "position": [1.0, 2.0, 3.0],
                        "rotation_degrees": [4.0, 5.0, 6.0],
                    },
                    "count": 630,
                    "spacing": 1.3,
                }
            ],
        )

    def test_figure_4_1_formula(self):
        points = vogel_points(4, divergence_angle=137.5, spacing=2.0)

        self.assertEqual(points[0].radius, 0.0)
        self.assertAlmostEqual(points[1].radius, 2.0)
        self.assertAlmostEqual(points[2].radius, 2.0 * math.sqrt(2.0))
        self.assertAlmostEqual(points[3].angle_degrees, 3.0 * 137.5)
        self.assertAlmostEqual(
            math.hypot(points[3].x, points[3].z), points[3].radius
        )

    def test_center_offset(self):
        point = vogel_points(1, center=(3.0, 4.0, 5.0))[0]
        self.assertEqual((point.x, point.y, point.z), (3.0, 4.0, 5.0))

    def test_optional_dome(self):
        points = vogel_points(5, height_function=dome_height(3.0))
        self.assertAlmostEqual(points[0].y, 3.0)
        self.assertAlmostEqual(points[-1].y, 0.0)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            vogel_points(-1)
        with self.assertRaises(ValueError):
            vogel_points(1, spacing=0.0)


if __name__ == "__main__":
    unittest.main()
