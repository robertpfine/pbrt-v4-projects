import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
    from vista_surface_texture import generate_vista_surface_mottle
    TEXTURE_DEPENDENCIES_AVAILABLE = True
except ModuleNotFoundError:
    TEXTURE_DEPENDENCIES_AVAILABLE = False


@unittest.skipUnless(
    TEXTURE_DEPENDENCIES_AVAILABLE,
    "vista texture generation requires NumPy and Pillow",
)
class VistaSurfaceTextureTests(unittest.TestCase):
    def test_map_is_deterministic_and_visibly_varied(self):
        config = {
            "resolution": 256,
            "seed": 41,
            "cluster_size": 0.20,
            "mottle_size": 0.02,
            "fine_size": 0.006,
            "coverage": 0.10,
            "softness": 0.08,
        }
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "first.png"
            second_path = Path(directory) / "second.png"
            generate_vista_surface_mottle(config, [0.07, 0.13, 0.22], first_path)
            generate_vista_surface_mottle(config, [0.07, 0.13, 0.22], second_path)
            first = np.asarray(Image.open(first_path))
            second = np.asarray(Image.open(second_path))

        self.assertEqual(first.shape, (256, 256, 3))
        self.assertTrue(np.array_equal(first, second))
        self.assertGreater(float(first.std()), 10.0)

    def test_resolution_must_support_fine_mottling(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "at least 256"):
                generate_vista_surface_mottle(
                    {"resolution": 128},
                    [0.07, 0.13, 0.22],
                    Path(directory) / "small.png",
                )


if __name__ == "__main__":
    unittest.main()
