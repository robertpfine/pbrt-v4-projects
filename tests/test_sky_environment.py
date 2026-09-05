from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
    from PIL import Image
    from sky_environment import generate_overcast_equal_area, generate_overcast_environment
    from scene_workspace.build_scene import write_lights
except ModuleNotFoundError:
    np = None
    Image = None
    generate_overcast_equal_area = None
    generate_overcast_environment = None
    write_lights = None


@unittest.skipUnless(generate_overcast_equal_area is not None, "sky map requires NumPy")
class OvercastEnvironmentTests(unittest.TestCase):
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
