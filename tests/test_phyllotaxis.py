import math
import unittest

from phyllotaxis import dome_height, vogel_points
from scene_objects import (
    configured_independent_geometry,
    configured_rgbgrid_media,
    configured_scene_objects,
)


class VogelPointTests(unittest.TestCase):
    def test_disabled_volume_objects_keep_geometry_and_owned_media(self):
        description = {
            "objects": [
                {
                    "name": "volume_sphere",
                    "enabled": False,
                    "placement": {
                        "position": [0, 0, 0],
                        "rotation_degrees": [20, 150, 0],
                    },
                    "geometry": {
                        "pbrt_shape": "sphere",
                        "parameters": {"radius": 1.5},
                    },
                    "material": {"type": "interface"},
                    "medium": {
                        "interior": {
                            "name": "volume_sphere_rgbgrid",
                            "type": "rgbgrid",
                            "zones": [{}],
                        },
                        "exterior": "",
                    },
                },
                {
                    "name": "volume_box",
                    "enabled": False,
                    "placement": {
                        "position": [0, 0, 0],
                        "rotation_degrees": [0, 0, 0],
                    },
                    "geometry": {"generator": "box"},
                    "material": {"type": "interface"},
                    "construction": {
                        "x_min": -1,
                        "x_max": 1,
                        "y_min": -2,
                        "y_max": 2,
                        "z_min": -3,
                        "z_max": 3,
                    },
                    "medium": {
                        "interior": {
                            "name": "volume_box_rgbgrid",
                            "type": "rgbgrid",
                            "zones": [{}],
                        },
                        "exterior": "",
                    },
                },
            ]
        }

        geometry = configured_independent_geometry(description)
        self.assertEqual([item["label"] for item in geometry], [
            "volume_sphere",
            "volume_box",
        ])
        self.assertEqual(geometry[0]["shape"], {"type": "sphere", "radius": 1.5})
        self.assertEqual(geometry[1]["shape"]["type"], "box")
        self.assertEqual(configured_rgbgrid_media(description), [])
        description["objects"][1]["enabled"] = True
        self.assertEqual(
            configured_rgbgrid_media(description)[0]["name"],
            "volume_box_rgbgrid",
        )

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
