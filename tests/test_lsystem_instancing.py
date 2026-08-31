from unittest import mock
import sys
import unittest

from fractal_tree import Segment

try:
    import noise  # noqa: F401
except ModuleNotFoundError:
    sys.modules["noise"] = mock.Mock(pnoise2=lambda *_args, **_kwargs: 0.0,
                                     pnoise3=lambda *_args, **_kwargs: 0.0)

try:
    import numpy  # noqa: F401
except ModuleNotFoundError:
    sys.modules["terrain_surface_texture"] = mock.Mock(
        generate_terrain_surface_maps=lambda *_args, **_kwargs: None
    )

from scene_workspace.build_scene import write_lsystem_trees


class LSystemInstancingTests(unittest.TestCase):
    def test_instances_share_local_geometry_and_keep_manual_positions(self):
        tree = {
            "enabled": True,
            "preset": "fractal_tree",
            "origin": [99.0, 88.0, 77.0],
            "scale": 2.5,
            "terrain_placement": {"enabled": False},
            "instances": [
                {"position": [-2.0, -8.0, -80.0], "rotation_y": 15.0},
                {"position": [-4.0, -9.0, -90.0], "scale": 0.5},
            ],
        }
        segment = Segment((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 1.0, 0.8, "wood")
        lines = []

        with mock.patch(
            "scene_workspace.build_scene.fractal_tree", return_value=[segment]
        ), mock.patch("scene_workspace.build_scene.write_oriented_cylinder") as write:
            write_lsystem_trees(lines, [tree])

        write.assert_called_once()
        self.assertEqual(write.call_args.args[1], (0.0, 0.0, 0.0))
        self.assertEqual(write.call_args.args[2], (0.0, 2.5, 0.0))
        output = "\n".join(lines)
        self.assertEqual(output.count('ObjectBegin "lsystem_fractal_tree_0"'), 1)
        self.assertEqual(output.count('ObjectInstance "lsystem_fractal_tree_0"'), 2)
        self.assertIn("Translate -2.000000000 -8.000000000 -80.000000000", output)
        self.assertIn("Translate -4.000000000 -9.000000000 -90.000000000", output)
        self.assertIn("Scale 0.500000000 0.500000000 0.500000000", output)

    def test_instance_scale_must_be_positive(self):
        tree = {
            "enabled": True,
            "preset": "fractal_tree",
            "instances": [{"position": [0.0, 0.0, 0.0], "scale": 0.0}],
        }
        segment = Segment((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 1.0, 0.8, "wood")

        with mock.patch(
            "scene_workspace.build_scene.fractal_tree", return_value=[segment]
        ), mock.patch("scene_workspace.build_scene.write_oriented_cylinder"):
            with self.assertRaisesRegex(ValueError, "instance scale must be positive"):
                write_lsystem_trees([], [tree])


if __name__ == "__main__":
    unittest.main()
