import unittest

from cloud_boundary_diagnostic import diagnose_formation, diagnostic_svg, project_point
from clouds import CloudFormation


class CloudBoundaryDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.camera = {
            "look_at": {
                "eye": [0.0, 0.0, 0.0],
                "look": [0.0, 0.0, -1.0],
                "up": [0.0, 1.0, 0.0],
            },
            "fov": 90.0,
        }
        self.film = {"x_resolution": 200, "y_resolution": 100}

    def test_projection_matches_pbrt_wide_screen_window(self):
        center = project_point((0.0, 0.0, -10.0), self.camera, self.film)
        right = project_point((20.0, 0.0, -10.0), self.camera, self.film)
        self.assertAlmostEqual(center["x"], 100.0)
        self.assertAlmostEqual(center["y"], 50.0)
        self.assertAlmostEqual(right["x"], 200.0)
        self.assertTrue(right["in_frame"])

    def test_diagnostic_reports_camera_and_writes_wireframe(self):
        formation = CloudFormation({
            "name": "visible_deck",
            "form": "mottled_veil",
            "center": [0, 0, -10],
            "size": [4, 4, 4],
            "boundary": {
                "mode": "corner_prism",
                "bottom_corners": {
                    "near_left": [-2, -1, -6],
                    "near_right": [2, -1, -6],
                    "far_right": [2, -2, -14],
                    "far_left": [-2, -2, -14],
                },
                "thickness": 3,
            },
        })
        result = diagnose_formation(formation, self.camera, self.film)
        self.assertFalse(result["camera_inside"])
        self.assertEqual(len(result["vertices"]), 8)
        self.assertTrue(all(vertex["in_front"] for vertex in result["vertices"]))
        svg = diagnostic_svg([result], self.film)
        self.assertIn("visible_deck (corner_prism)", svg)
        self.assertIn("<line", svg)


if __name__ == "__main__":
    unittest.main()
