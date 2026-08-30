import unittest

from terrain import RollingHillside
from terrain_details import (
    _camera_frame,
    _instance_anchor_position,
    _point_inside_camera_frustum,
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
            },
        }

    def test_requested_count_uses_visible_ground_placements(self):
        points = scatter_points(
            self.terrain,
            self.config,
            camera=self.camera,
            film=self.film,
        )
        self.assertEqual(len(points), self.config["count"])

        frame = _camera_frame(self.camera, self.film)
        for point in points:
            self.assertTrue(_point_inside_camera_frustum(point.position, frame))

    def test_enabled_constraint_requires_camera(self):
        with self.assertRaisesRegex(ValueError, "requires a camera"):
            scatter_points(self.terrain, self.config)

    def test_point_near_image_edge_is_not_inset_for_object_bounds(self):
        frame = _camera_frame(self.camera, self.film)
        self.assertTrue(_point_inside_camera_frustum((10.0, 0.0, 0.0), frame))

    def test_object_anchor_not_root_controls_visible_instance_count(self):
        anchor = (0.0, 3.0, 0.0)
        points = scatter_points(
            self.terrain,
            {**self.config, "count": 1000},
            camera=self.camera,
            film=self.film,
            visibility_anchor=anchor,
        )
        frame = _camera_frame(self.camera, self.film)
        self.assertEqual(len(points), 1000)
        self.assertTrue(any(
            not _point_inside_camera_frustum(point.position, frame)
            for point in points
        ))
        for point in points:
            self.assertTrue(_point_inside_camera_frustum(
                _instance_anchor_position(point, anchor),
                frame,
            ))

    def test_disabled_constraint_retains_camera_independent_scatter(self):
        config = dict(self.config)
        config["camera_frustum"] = {"enabled": False}
        first = scatter_points(self.terrain, config)
        second = scatter_points(self.terrain, config)
        self.assertEqual(first, second)
        self.assertEqual(len(first), config["count"])


if __name__ == "__main__":
    unittest.main()
