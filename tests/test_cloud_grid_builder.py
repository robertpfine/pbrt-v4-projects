import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from cloud_grid_contract import normalized_cloud_job, run_compiled_builder, write_job
from clouds import CloudFormation


ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / "build" / "cloud_grid_builder" / "cloud_grid_builder"


def pbrt_array(source: str, declaration: str) -> list[float]:
    match = re.search(
        rf'"{re.escape(declaration)}"\s*\[(.*?)\]', source, flags=re.DOTALL
    )
    if not match:
        raise AssertionError(f"PBRT array not found: {declaration}")
    return [float(value) for value in match.group(1).split()]


class CompiledCloudGridParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            [str(ROOT / "build_cloud_grid_builder.sh")],
            check=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def compile_formation(self, shared, formation, threads=1):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            job_path = directory / "job.json"
            output_path = directory / "medium.pbrt"
            write_job(normalized_cloud_job(shared, formation), job_path)
            run_compiled_builder(job_path, output_path, EXECUTABLE, threads)
            return output_path.read_text(encoding="utf-8")

    def assert_grid_close(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        maximum_error = max(
            (abs(left - right) for left, right in zip(actual, expected)),
            default=0.0,
        )
        self.assertLessEqual(maximum_error, 1.1e-5)

    def test_lobed_density_matches_python_reference(self):
        shared = {
            "appearance": {
                "density": 0.88,
                "scattering": [0.006, 0.005, 0.004],
                "absorption": [0.0001, 0.0002, 0.0003],
                "anisotropy": 0.2,
            },
            "shape": {"bottom_fade": 80.0, "top_fade": 120.0},
            "fractal_noise": {
                "seed": 17,
                "frequency": [0.002, 0.0025, 0.0018],
                "octaves": 2.5,
                "roughness": 0.53,
                "frequency_jump": 2.0,
                "coverage": 0.10,
                "softness": 0.22,
                "edge_influence": 0.28,
                "density_contrast": 0.65,
                "density_modulation_min": 0.35,
                "density_modulation_max": 1.35,
                "envelope_power": 0.5,
                "domain_warp": {
                    "enabled": True,
                    "frequency": [0.0015, 0.0012, 0.0017],
                    "strength": [120.0, 80.0, 110.0],
                },
            },
        }
        formation = {
            "name": "parity_lobed",
            "form": "lobed",
            "center": [100.0, 500.0, -800.0],
            "size": [700.0, 420.0, 600.0],
            "resolution": [9, 7, 8],
            "lobes": [
                {
                    "center_offset": [-80.0, -20.0, 30.0],
                    "radii": [250.0, 150.0, 220.0],
                    "strength": 1.0,
                },
                {
                    "center_offset": [120.0, 60.0, -40.0],
                    "radii": [190.0, 180.0, 170.0],
                    "strength": 0.92,
                },
            ],
        }
        source = self.compile_formation(shared, formation)
        actual = pbrt_array(source, "float density")
        expected = CloudFormation(formation, shared).density_grid()
        self.assert_grid_close(actual, expected)

    def test_mottled_rgb_grids_match_python_reference(self):
        shared = {
            "appearance": {
                "density": 0.9,
                "scattering": [0.0028, 0.0030, 0.0032],
                "absorption": [0.00045, 0.00050, 0.00055],
                "anisotropy": 0.25,
                "underside": {
                    "enabled": True,
                    "height_fraction": 0.5,
                    "transition": 0.25,
                    "scattering_scale": 0.45,
                    "absorption_scale": 3.2,
                },
            },
            "shape": {"bottom_fade": 120.0, "top_fade": 180.0},
            "fractal_noise": {
                "seed": 823,
                "frequency": [0.00045, 0.0012, 0.00055],
                "octaves": 3.0,
                "roughness": 0.55,
                "frequency_jump": 2.0,
                "coverage": 0.34,
                "softness": 0.22,
                "broad_strength": 1.0,
                "detail_strength": 0.35,
                "detail_frequency_scale": 2.7,
                "edge_fade_fraction": [0.08, 0.15, 0.1],
                "domain_warp": {
                    "enabled": False,
                    "frequency": 0.001,
                    "strength": [0.0, 0.0, 0.0],
                },
            },
        }
        formation = {
            "name": "parity_overcast",
            "form": "mottled_veil",
            "center": [-1500.0, 850.0, -1000.0],
            "size": [5000.0, 800.0, 2600.0],
            "resolution": [11, 8, 10],
            "depth_slope": {"enabled": True, "far_y_offset": -300.0},
            "depth_profile": {
                "enabled": True,
                "full_density_until_z": -1200.0,
                "falloff_distance": 900.0,
                "far_density_scale": 0.2,
            },
        }
        source = self.compile_formation(shared, formation)
        actual_absorption = pbrt_array(source, "rgb sigma_a")
        actual_scattering = pbrt_array(source, "rgb sigma_s")
        expected_absorption, expected_scattering = CloudFormation(
            formation, shared
        ).optical_grids()
        self.assert_grid_close(actual_absorption, expected_absorption)
        self.assert_grid_close(actual_scattering, expected_scattering)

    def test_thread_counts_are_deterministic(self):
        shared = {
            "appearance": {"density": 1.0},
            "fractal_noise": {"seed": 11},
        }
        formation = {
            "name": "thread_parity",
            "center": [0.0, 0.0, 0.0],
            "size": [1000.0, 500.0, 800.0],
            "resolution": [12, 9, 10],
            "lobes": [
                {
                    "center_offset": [0.0, 0.0, 0.0],
                    "radii": [450.0, 220.0, 350.0],
                }
            ],
        }
        single = self.compile_formation(shared, formation, threads=1)
        parallel = self.compile_formation(shared, formation, threads=4)
        self.assertEqual(single, parallel)

    def test_adapter_rejects_dangerous_thread_count(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 256"):
            run_compiled_builder(
                Path("job.json"), Path("medium.pbrt"), EXECUTABLE, threads=-1
            )


if __name__ == "__main__":
    unittest.main()
