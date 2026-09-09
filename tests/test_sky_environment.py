from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
    from PIL import Image
    from sky_environment import generate_overcast_equal_area, generate_overcast_environment
    from sky_environment import generate_twilight_equal_area, _equal_area_square_to_sphere
    from scene_workspace.build_scene import write_lights
except ModuleNotFoundError:
    np = None
    Image = None
    generate_overcast_equal_area = None
    generate_overcast_environment = None
    write_lights = None


@unittest.skipUnless(generate_overcast_equal_area is not None, "sky map requires NumPy")
class OvercastEnvironmentTests(unittest.TestCase):
    def test_twilight_stars_are_seeded_and_confined_to_upper_sky(self):
        config = {"resolution": [512, 512], "star_count": 12,
                  "star_radius_degrees": 0.25, "seed": 73}
        stars = generate_twilight_equal_area(config)
        self.assertTrue(np.array_equal(stars, generate_twilight_equal_area(config)))
        base = generate_twilight_equal_area({**config, "star_count": 0})
        y = _equal_area_square_to_sphere(512, 512)[1]
        self.assertTrue(np.array_equal(stars[y < 0], base[y < 0]))
        self.assertGreater(float((stars - base).max()), 1.0)
        changed = generate_twilight_equal_area({**config, "seed": 74})
        self.assertFalse(np.array_equal(stars, changed))
        for name, value in (("star_count", -1), ("star_radius_degrees", 0),
                            ("star_brightness", float("nan"))):
            with self.subTest(field=name), self.assertRaises(ValueError):
                generate_twilight_equal_area({**config, name: value})

    def test_twilight_tracks_world_y_and_is_continuous_at_horizon(self):
        config = {"resolution": [512, 512],
                  "zenith_color": [0.1, 0.2, 0.4],
                  "horizon_color": [0.5, 0.3, 0.2],
                  "nadir_color": [0.02, 0.03, 0.04]}
        color = generate_twilight_equal_area(config)
        y = _equal_area_square_to_sphere(512, 512)[1]
        self.assertTrue(np.allclose(color[y > 0.9], config["zenith_color"]))
        self.assertTrue(np.allclose(color[y < -0.9], config["nadir_color"]))
        self.assertTrue(np.allclose(color[np.abs(y) < 0.001],
                                    config["horizon_color"], atol=1e-5))
        self.assertTrue(np.all(np.isfinite(color)))

    def test_twilight_builder_writes_map_and_rejects_invalid_controls(self):
        from scene_workspace.build_scene import configured_background_light
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            light = configured_background_light(None, {"background": {
                "source": "procedural_twilight", "scale": 0.24,
                "environment": {"generator": "twilight_map", "resolution": [512, 512]}
            }}, root, root / "scene_files")
            path = root / light["environment_filename"]
            self.assertTrue(path.read_bytes().startswith(b"PF\n512 512\n-1.0\n"))
            self.assertEqual(light["scale"], 0.24)
        for bad in (0, 91, float("nan"), True):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                generate_twilight_equal_area({"resolution": [512, 512],
                                             "horizon_transition_degrees": bad})

    def config(self):
        return {
            "resolution": [512, 512],
            "seed": 823,
            "coverage": 0.88,
            "softness": 0.16,
            "target_average_color": [0.62, 0.68, 0.75],
        }

    def test_equal_area_generation_is_deterministic_and_nonuniform(self):
        with tempfile.TemporaryDirectory() as directory:
            first_dir = Path(directory) / "first"
            second_dir = Path(directory) / "second"
            first = generate_overcast_environment(self.config(), first_dir)
            second = generate_overcast_environment(self.config(), second_dir)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(
                first_dir.joinpath("overcast_environment_equalarea.png").read_bytes(),
                second_dir.joinpath("overcast_environment_equalarea.png").read_bytes(),
            )
            color = generate_overcast_equal_area(self.config())
            self.assertGreater(float(color.std()), 0.02)
            self.assertTrue(np.allclose(
                color.mean(axis=(0, 1)), [0.62, 0.68, 0.75], atol=2e-4
            ))

    def test_equal_area_generation_rejects_non_square_resolution(self):
        config = self.config()
        config["resolution"] = [1024, 512]
        with self.assertRaisesRegex(ValueError, "square"):
            generate_overcast_equal_area(config)

    def test_image_infinite_light_replaces_uniform_radiance(self):
        lines = []
        write_lights(lines, [{
            "enabled": True,
            "type": "infinite",
            "scale": 0.16,
            "environment_filename": "scene_workspace/scene_files/textures/sky.exr",
            "environment_rotation_degrees": 15.0,
        }])
        text = "\n".join(lines)
        self.assertIn('Rotate 15.0 0 1 0', text)
        self.assertIn('"string filename"', text)
        self.assertIn('textures/sky.exr', text)
        self.assertNotIn('"rgb L"', text)

    def test_uniform_infinite_light_output_is_unchanged(self):
        lines = []
        write_lights(lines, [{
            "enabled": True,
            "type": "infinite",
            "color_mode": "rgb",
            "color": [0.62, 0.68, 0.75],
            "scale": 0.16,
        }])
        self.assertEqual(
            lines,
            [
                'LightSource "infinite"  "rgb L" [ 0.62 0.68 0.75 ]'
                '  "float scale" [ 0.16 ]',
                "",
            ],
        )


if __name__ == "__main__":
    unittest.main()
