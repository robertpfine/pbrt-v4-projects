import unittest

from terrain import RollingHillside
from terrain_details import (
    _camera_frame,
    _sphere_inside_camera_frustum,
    scatter_points,
)


class CameraFrustumScatterTests(unittest.TestCase):
    def setUp(self):
        self.terrain = RollingHillside({
            "size": [80.0, 80.0],
            "resolution": [9, 9],
            "noise": {"amplitude": 0.0},
        })
        self.camera = {
            "look_at": {
                "eye": [0.0, 8.0, 20.0],
                "look": [0.0, 0.0, 0.0],
                "up": [0.0, 1.0, 0.0],
            },
            "fov": 60.0,
        }
        self.film = {"x_resolution": 1200, "y_resolution": 1200}
        self.config = {
            "enabled": True,
            "count": 100,
            "seed": 17,
            "region": {"center": [0.0, 0.0], "size": [80.0, 80.0]},
            "scale": [0.5, 1.5],
            "variants": 3,
            "camera_frustum": {
                "enabled": True,
                "frame_margin": 0.03,
                "bounds_radius": 0.8,
            },
        }

    def test_requested_count_fits_completely_inside_camera(self):
        points = scatter_points(
            self.terrain,
            self.config,
            camera=self.camera,
            film=self.film,
        )
        self.assertEqual(len(points), self.config["count"])

        frustum = self.config["camera_frustum"]
        frame = _camera_frame(
            self.camera, self.film, frustum["frame_margin"]
        )
        for point in points:
            radius = frustum["bounds_radius"] * point.scale * max(point.aspect)
            self.assertTrue(
                _sphere_inside_camera_frustum(point.position, radius, frame)
            )

    def test_enabled_constraint_requires_camera(self):
        with self.assertRaisesRegex(ValueError, "requires a camera"):
            scatter_points(self.terrain, self.config)

    def test_disabled_constraint_retains_camera_independent_scatter(self):
        config = dict(self.config)
        config["camera_frustum"] = {"enabled": False}
        first = scatter_points(self.terrain, config)
        second = scatter_points(self.terrain, config)
        self.assertEqual(first, second)
        self.assertEqual(len(first), config["count"])


if __name__ == "__main__":
    unittest.main()
