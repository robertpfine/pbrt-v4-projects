import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from render_snapshot import (
    RenderSnapshotError,
    cleanup_snapshot,
    create_snapshot,
    finalize_snapshot,
    sha256_file,
)

try:
    import render_shaft_composite
except ModuleNotFoundError:
    render_shaft_composite = None


class RenderSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.scene_root = self.root / "scene_workspace"
        self.scene_root.mkdir()
        (self.root / "render_pipeline.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        (self.root / "render_snapshot.py").write_text("# snapshot helper\n", encoding="utf-8")
        (self.scene_root / "build_scene.py").write_text("# builder\n", encoding="utf-8")
        self.config = self.scene_root / "config.json"
        self.config.write_text(
            json.dumps(
                {
                    "scene": {
                        "name": "Original Scene",
                        "master_file": "scene_files/scene.pbrt",
                    }
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_snapshot_is_unchanged_when_live_inputs_change(self):
        result = create_snapshot(self.root, self.config, "20260904_010203")
        snapshot_config = Path(result["config"])
        original_hash = sha256_file(snapshot_config)

        self.config.write_text(
            json.dumps({"scene": {"name": "Changed Scene"}}) + "\n",
            encoding="utf-8",
        )
        (self.scene_root / "build_scene.py").write_text("# changed\n", encoding="utf-8")

        self.assertEqual(sha256_file(snapshot_config), original_hash)
        self.assertEqual(
            json.loads(snapshot_config.read_text(encoding="utf-8"))["scene"]["name"],
            "Original Scene",
        )

    def test_finalize_archives_frozen_config_sources_artifacts_and_hashes(self):
        result = create_snapshot(self.root, self.config, "20260904_010204")
        archive = self.root / "Archive"
        prefix = archive / "Original_Scene_20260904_010204"
        rendered_scene = Path(result["scene_root"]) / "scene_files" / "scene.pbrt"
        rendered_scene.parent.mkdir(parents=True)
        rendered_scene.write_text("WorldBegin\n", encoding="utf-8")
        rendered_image = Path(str(prefix) + ".png")
        rendered_image.parent.mkdir()
        rendered_image.write_bytes(b"fake png")

        manifest_path = finalize_snapshot(
            Path(result["run_directory"]),
            prefix,
            ((".png", rendered_image), (".pbrt", rendered_scene)),
        )

        self.assertEqual(
            json.loads(Path(str(prefix) + "_config.json").read_text())["scene"]["name"],
            "Original Scene",
        )
        self.assertTrue(Path(str(prefix) + "_snapshot_sources.tar.gz").is_file())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["artifacts"][prefix.name + ".pbrt"],
            sha256_file(Path(str(prefix) + ".pbrt")),
        )
        self.assertIn(prefix.name + ".png", manifest["artifacts"])

    def test_cleanup_refuses_directory_outside_render_workspace(self):
        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        (unrelated / "input_manifest.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(RenderSnapshotError):
            cleanup_snapshot(self.root, unrelated)
        self.assertTrue(unrelated.is_dir())

    def test_snapshot_rejects_master_file_outside_frozen_workspace(self):
        self.config.write_text(
            json.dumps(
                {
                    "scene": {
                        "name": "Unsafe Scene",
                        "master_file": "../live_scene.pbrt",
                    }
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            RenderSnapshotError, "inside the frozen scene workspace"
        ):
            create_snapshot(self.root, self.config, "20260904_010206")

    def test_snapshot_freezes_configured_cloud_grid_executable(self):
        executable = self.root / "build" / "cloud_grid_builder" / "cloud_grid_builder"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"compiled cloud builder")
        executable.chmod(0o755)
        shutil.copy2(Path("cloud_grid_contract.py"), self.root / "cloud_grid_contract.py")
        self.config.write_text(
            json.dumps(
                {
                    "scene": {
                        "name": "Compiled Scene",
                        "master_file": "scene_files/scene.pbrt",
                        "sky": {
                            "clouds": {
                                "grid_builder": {
                                    "backend": "cpp",
                                    "executable": (
                                        "build/cloud_grid_builder/cloud_grid_builder"
                                    ),
                                    "fallback_to_python": False,
                                }
                            }
                        },
                    }
                }
            ),
            encoding="utf-8",
        )

        result = create_snapshot(self.root, self.config, "20260904_010207")
        frozen = (
            Path(result["repository_root"])
            / "build"
            / "cloud_grid_builder"
            / "cloud_grid_builder"
        )
        self.assertEqual(frozen.read_bytes(), b"compiled cloud builder")
        self.assertTrue(frozen.stat().st_mode & 0o111)
        frozen_perlin = (
            Path(result["repository_root"])
            / "render_dependencies"
            / "cloud_perlin.so"
        )
        self.assertTrue(frozen_perlin.is_file())
        manifest = json.loads(
            (Path(result["run_directory"]) / "input_manifest.json").read_text()
        )
        self.assertIn("render_dependencies/cloud_perlin.so", manifest["files"])
        completed = subprocess.run(
            [
                "python3",
                "-c",
                "from cloud_grid_contract import _native_noise_library; "
                "print(_native_noise_library())",
            ],
            cwd=result["repository_root"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.stdout.strip(), str(frozen_perlin))

    def test_snapshot_allows_missing_compiled_builder_with_explicit_fallback(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["scene"]["sky"] = {
            "clouds": {
                "grid_builder": {
                    "backend": "cpp",
                    "executable": "build/cloud_grid_builder/missing",
                    "fallback_to_python": True,
                }
            }
        }
        self.config.write_text(json.dumps(config), encoding="utf-8")

        result = create_snapshot(self.root, self.config, "20260904_010211")

        self.assertTrue(Path(result["config"]).is_file())

    def test_finalize_archives_normalized_cloud_job(self):
        result = create_snapshot(self.root, self.config, "20260904_010208")
        cloud_jobs = (
            Path(result["scene_root"]) / "scene_files" / "cloud_grid_jobs"
        )
        cloud_jobs.mkdir(parents=True)
        (cloud_jobs / "cloud_0_test.json").write_text(
            '{"contract_version": 1}\n', encoding="utf-8"
        )
        archive = self.root / "Archive"
        prefix = archive / "Original_Scene_20260904_010208"
        artifact = self.root / "render.png"
        artifact.write_bytes(b"fake png")

        finalize_snapshot(
            Path(result["run_directory"]), prefix, ((".png", artifact),)
        )

        archived_job = Path(
            str(prefix) + "_cloud_job_cloud_0_test.json"
        )
        self.assertEqual(
            json.loads(archived_job.read_text(encoding="utf-8")),
            {"contract_version": 1},
        )


class RenderPipelineSnapshotIntegrationTests(unittest.TestCase):
    def test_pipeline_builds_and_archives_from_frozen_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scene_root = root / "scene_workspace"
            scene_root.mkdir()
            shutil.copy2(Path("render_pipeline.sh"), root / "render_pipeline.sh")
            shutil.copy2(Path("render_snapshot.py"), root / "render_snapshot.py")

            fake_pbrt = root / "fake_pbrt.sh"
            fake_pbrt.write_text(
                "#!/usr/bin/env bash\n"
                "while [ $# -gt 0 ]; do\n"
                "  if [ \"$1\" = \"--outfile\" ]; then output=$2; shift 2; else shift; fi\n"
                "done\n"
                "printf 'fake image' > \"$output\"\n",
                encoding="utf-8",
            )
            fake_pbrt.chmod(0o755)

            builder = scene_root / "build_scene.py"
            builder.write_text(
                "import json, os, sys, time\n"
                "config_path = sys.argv[1]\n"
                "with open(config_path) as handle: config = json.load(handle)\n"
                "time.sleep(0.2)\n"
                "root = os.path.dirname(config_path)\n"
                "path = os.path.join(root, config['scene']['master_file'])\n"
                "os.makedirs(os.path.dirname(path), exist_ok=True)\n"
                "with open(path, 'w') as handle: "
                "handle.write('# SCENE: ' + config['scene']['name'] + '\\nWorldBegin\\n')\n",
                encoding="utf-8",
            )

            config_path = scene_root / "config.json"
            config = {
                "archive": {"remote_path": "unused:"},
                "runtime": {
                    "pbrt_binary": str(fake_pbrt),
                    "use_gpu": False,
                    "show_stats": False,
                },
                "pipeline": {
                    "build_scene": {"enabled": True},
                    "rclone_sync": {"enabled": False},
                },
                "scene": {
                    "name": "Original Scene",
                    "master_file": "scene_files/scene.pbrt",
                    "trees": [],
                },
            }
            config_path.write_text(json.dumps(config), encoding="utf-8")

            process = subprocess.Popen(
                [str(root / "render_pipeline.sh"), str(config_path)],
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            output_lines = []
            assert process.stdout is not None
            for line in process.stdout:
                output_lines.append(line)
                if line.startswith("Render inputs frozen:"):
                    config["scene"]["name"] = "Changed Scene"
                    config_path.write_text(json.dumps(config), encoding="utf-8")
                if line.startswith("Pipeline complete:"):
                    break
            process.wait(timeout=10)
            remaining = process.stdout.read()
            process.stdout.close()
            output = "".join(output_lines) + remaining

            self.assertEqual(process.returncode, 0, output)
            archived_configs = list((root / "Archive").glob("Original_Scene_*_config.json"))
            self.assertEqual(len(archived_configs), 1)
            archived_config = json.loads(archived_configs[0].read_text(encoding="utf-8"))
            self.assertEqual(archived_config["scene"]["name"], "Original Scene")
            archived_scenes = list((root / "Archive").glob("Original_Scene_*.pbrt"))
            self.assertEqual(len(archived_scenes), 1)
            self.assertIn("# SCENE: Original Scene", archived_scenes[0].read_text())
            self.assertEqual(
                list((scene_root / ".render_runs").iterdir()),
                [],
            )


@unittest.skipIf(
    render_shaft_composite is None,
    "shaft-composite NumPy/Pillow dependencies are unavailable",
)
class ShaftCompositeSnapshotTests(unittest.TestCase):
    def test_entry_point_reexecutes_the_frozen_script_and_config(self):
        result = {
            "run_directory": "/repo/scene_workspace/.render_runs/20260904_010205",
            "repository_root": "/repo/scene_workspace/.render_runs/"
            "20260904_010205/repository",
            "config": "/repo/scene_workspace/.render_runs/20260904_010205/"
            "repository/scene_workspace/config.json",
        }
        with mock.patch.dict(render_shaft_composite.os.environ, {}, clear=False):
            render_shaft_composite.os.environ.pop("PBRT_RENDER_SNAPSHOT_DIR", None)
            with mock.patch.object(
                render_shaft_composite, "create_snapshot", return_value=result
            ), mock.patch.object(
                render_shaft_composite.os,
                "execve",
                side_effect=RuntimeError("re-executed"),
            ) as execute:
                with self.assertRaisesRegex(RuntimeError, "re-executed"):
                    render_shaft_composite.activate_snapshot(
                        "/repo", "/repo/scene_workspace/config.json"
                    )

        executable, arguments, environment = execute.call_args.args
        self.assertEqual(executable, render_shaft_composite.sys.executable)
        self.assertEqual(arguments[-1], result["config"])
        self.assertEqual(environment["PBRT_RENDER_SNAPSHOT_DIR"], result["run_directory"])
        self.assertEqual(environment["PBRT_LIVE_REPOSITORY_ROOT"], "/repo")


if __name__ == "__main__":
    unittest.main()
