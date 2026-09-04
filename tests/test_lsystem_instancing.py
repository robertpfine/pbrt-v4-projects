from unittest import mock
from pathlib import Path
import sys
import tempfile
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
    sys.modules["vista_surface_texture"] = mock.Mock(
        generate_vista_surface_mottle=lambda *_args, **_kwargs: None
    )

from scene_workspace.build_scene import (
    configured_filename,
    configured_scene_files,
    write_camera,
    write_film,
    write_geometry,
    write_integrator,
    write_lsystem_trees,
    write_sampler,
)


class ConfiguredFileLayoutTests(unittest.TestCase):
    def test_scene_builder_resolves_repository_relative_scene_files(self):
        with tempfile.TemporaryDirectory() as directory:
            scene_root = Path(directory) / "working_scene"
            scene_root.mkdir()
            config = {"file_paths": {"scene_files": "generated/scenes"}}
            self.assertEqual(
                configured_scene_files(config, scene_root),
                Path(directory) / "generated" / "scenes",
            )

    def test_scene_builder_rejects_escaping_scene_files_path(self):
        with tempfile.TemporaryDirectory() as directory:
            scene_root = Path(directory) / "working_scene"
            scene_root.mkdir()
            config = {"file_paths": {"scene_files": "../outside"}}
            with self.assertRaisesRegex(ValueError, "inside the repository"):
                configured_scene_files(config, scene_root)

    def test_scene_builder_rejects_escaping_configured_filename(self):
        config = {"file_names": {"pbrt_scene": "../outside.pbrt"}}
        with self.assertRaisesRegex(ValueError, "filename without a directory"):
            configured_filename(config, "pbrt_scene")

    def test_camera_writer_uses_explicit_supported_type(self):
        lines = []
        camera = {
            "enabled": True,
            "type": "perspective",
            "look_at": {
                "eye": [0, 1, 2],
                "look": [0, 0, 0],
                "up": [0, 1, 0],
            },
            "fov": 50.0,
        }
        write_camera(lines, camera)
        self.assertIn('Camera "perspective"  "float fov" [ 50.0 ]', lines)
        camera["type"] = "orthographic"
        with self.assertRaisesRegex(ValueError, "unsupported camera_settings.type"):
            write_camera([], camera)

    def test_render_directive_writers_reject_unsupported_or_invalid_values(self):
        with self.assertRaisesRegex(ValueError, "unsupported render_settings.sampler"):
            write_sampler([], {"type": "random", "pixel_samples": 4})
        with self.assertRaisesRegex(ValueError, "pixel_samples must be positive"):
            write_sampler([], {"type": "halton", "pixel_samples": 0})
        with self.assertRaisesRegex(ValueError, "unsupported render_settings.integrator"):
            write_integrator([], {"type": "path", "max_depth": 8})
        with self.assertRaisesRegex(ValueError, "max_depth must be positive"):
            write_integrator([], {"type": "volpath", "max_depth": False})
        with self.assertRaisesRegex(ValueError, "resolution must be positive"):
            write_film([], {"x_resolution": 100, "y_resolution": 0}, "image.png")


class GeometryMaterialTests(unittest.TestCase):
    def test_diffuse_scale_multiplies_reflectance(self):
        geometry = [{
            "enabled": True,
            "label": "vista_plane",
            "material": {
                "type": "diffuse",
                "reflectance": [0.35, 0.60, 1.00],
                "scale": 0.22,
            },
            "shape": {"type": "disk", "radius": 1.0},
        }]
        lines = []

        write_geometry(lines, geometry)

        self.assertIn(
            '    Material "diffuse"  "rgb reflectance" [ 0.077 0.132 0.22 ]',
            lines,
        )

    def test_diffuse_scale_cannot_be_negative(self):
        geometry = [{
            "enabled": True,
            "material": {
                "type": "diffuse",
                "reflectance": [0.35, 0.60, 1.00],
                "scale": -1.0,
            },
            "shape": {"type": "disk", "radius": 1.0},
        }]

        with self.assertRaisesRegex(ValueError, "scale cannot be negative"):
            write_geometry([], geometry)

    def test_bilinear_surface_mottle_uses_generated_texture_and_uvs(self):
        geometry = [{
            "enabled": True,
            "label": "vista_plane",
            "material": {
                "type": "diffuse",
                "reflectance": [0.35, 0.60, 1.00],
                "scale": 0.22,
                "surface_mottle": {"enabled": True},
            },
            "shape": {
                "type": "bilinearmesh",
                "indices": [0, 1, 2, 3],
                "points": [0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1],
            },
        }]
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "scene_workspace.build_scene.generate_vista_surface_mottle",
            return_value=Path(directory) / "mottle.png",
        ):
            lines = []
            write_geometry(lines, geometry, directory)

        output = "\n".join(lines)
        self.assertIn('Texture "vista_plane_surface_mottle"', output)
        self.assertIn('"texture reflectance" [ "vista_plane_surface_mottle" ]', output)
        self.assertIn('"point2 uv"', output)


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
