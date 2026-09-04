import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
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
                    "file_names": {
                        "pbrt_scene": "scene.pbrt",
                        "working_image": "working.png",
                        "archive_image": "{scene_name}_{timestamp}.png",
                    },
                    "file_paths": {
                        "scene_files": "scene_workspace/scene_files",
                        "local_archive": "Archive",
                        "remote_archive": "unused:",
                        "pbrt_executable": "/usr/bin/false",
                    },
                    "camera_settings": {
                        "enabled": True,
                        "type": "perspective",
                        "look_at": {
                            "eye": [0, 1, 2],
                            "look": [0, 0, 0],
                            "up": [0, 1, 0],
                        },
                        "fov": 50.0,
                    },
                    "render_settings": {
                        "film": {"x_resolution": 100, "y_resolution": 100},
                        "sampler": {"type": "halton", "pixel_samples": 4},
                        "integrator": {"type": "volpath", "max_depth": 8},
                        "backend": {"type": "cpu", "show_statistics": False},
                        "shaft_composite": {
                            "enabled": False,
                            "shaft_light": "shaft_sun",
                            "base_opacity": 1.0,
                            "shaft_opacity": 0.4,
                            "surface_reflectance_scale": 0.08,
                            "terrain_reflectance_scale": 0.015,
                            "blur_radius": 2.0,
                        },
                    },
                    "scene": {"name": "Original Scene"},
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

    def test_snapshot_resolves_configured_archive_pattern_and_directory(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["file_names"]["archive_image"] = (
            "proof-{scene_name}-{timestamp}.png"
        )
        config["file_paths"]["local_archive"] = "SavedRenders"
        self.config.write_text(json.dumps(config), encoding="utf-8")

        result = create_snapshot(self.root, self.config, "20260904_010212")

        self.assertEqual(
            Path(result["archive_directory"]),
            self.root / "SavedRenders",
        )
        self.assertEqual(
            Path(result["archive_image"]),
            self.root
            / "SavedRenders"
            / "proof-Original_Scene-20260904_010212.png",
        )

    def test_snapshot_rejects_pbrt_scene_with_directory(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["file_names"]["pbrt_scene"] = "scene_files/scene.pbrt"
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(
            RenderSnapshotError, "filename without a directory"
        ):
            create_snapshot(self.root, self.config, "20260904_010213")

    def test_snapshot_rejects_dot_dot_as_a_filename(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["file_names"]["working_image"] = ".."
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(
            RenderSnapshotError, "filename without a directory"
        ):
            create_snapshot(self.root, self.config, "20260904_010214")

    def test_finalize_archives_frozen_config_sources_artifacts_and_hashes(self):
        result = create_snapshot(self.root, self.config, "20260904_010204")
        archive = self.root / "Archive"
        prefix = archive / "Original_Scene_20260904_010204"
        rendered_scene = Path(result["scene_files"]) / "scene.pbrt"
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

    def test_snapshot_rejects_scene_files_outside_frozen_repository(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["scene"]["name"] = "Unsafe Scene"
        config["file_paths"]["scene_files"] = "../live_scene"
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(
            RenderSnapshotError, "inside the frozen repository"
        ):
            create_snapshot(self.root, self.config, "20260904_010206")

    def test_snapshot_rejects_repository_root_as_scene_files(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["file_paths"]["scene_files"] = "."
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(
            RenderSnapshotError, "inside the frozen repository"
        ):
            create_snapshot(self.root, self.config, "20260904_010215")

    def test_snapshot_rejects_obsolete_stage_one_keys(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["scene"]["master_file"] = "scene_files/scene.pbrt"
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(
            RenderSnapshotError, "obsolete scene.master_file"
        ):
            create_snapshot(self.root, self.config, "20260904_010216")

    def test_snapshot_rejects_obsolete_scene_camera(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["scene"]["camera"] = config["camera_settings"]
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(RenderSnapshotError, "obsolete scene.camera"):
            create_snapshot(self.root, self.config, "20260904_010217")

    def test_snapshot_rejects_obsolete_render_roots(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["runtime"] = {"use_gpu": False}
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(RenderSnapshotError, "obsolete runtime root"):
            create_snapshot(self.root, self.config, "20260904_010218")

    def test_snapshot_freezes_configured_cloud_grid_executable(self):
        executable = self.root / "build" / "cloud_grid_builder" / "cloud_grid_builder"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"compiled cloud builder")
        executable.chmod(0o755)
        shutil.copy2(Path("cloud_grid_contract.py"), self.root / "cloud_grid_contract.py")
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["scene"] = {
            "name": "Compiled Scene",
            "sky": {
                "clouds": {
                    "grid_builder": {
                        "backend": "cpp",
                        "executable": "build/cloud_grid_builder/cloud_grid_builder",
                        "fallback_to_python": False,
                    }
                }
            },
        }
        self.config.write_text(json.dumps(config), encoding="utf-8")

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
    def test_pipeline_rejects_invalid_backend_before_scene_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scene_root = root / "scene_workspace"
            scene_root.mkdir()
            shutil.copy2(Path("render_pipeline.sh"), root / "render_pipeline.sh")
            shutil.copy2(Path("render_snapshot.py"), root / "render_snapshot.py")
            marker = root / "builder-ran"
            builder = scene_root / "build_scene.py"
            builder.write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).touch()\n",
                encoding="utf-8",
            )
            config = {
                "file_names": {
                    "pbrt_scene": "scene.pbrt",
                    "working_image": "working.png",
                    "archive_image": "{scene_name}_{timestamp}.png",
                },
                "file_paths": {
                    "scene_files": "scene_workspace/scene_files",
                    "local_archive": "Archive",
                    "remote_archive": "unused:",
                    "pbrt_executable": "/usr/bin/false",
                },
                "camera_settings": {},
                "render_settings": {
                    "backend": {"type": "vulkan", "show_statistics": False},
                    "shaft_composite": {"enabled": False},
                },
                "scene": {"name": "Invalid Backend"},
            }
            config_path = scene_root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            completed = subprocess.run(
                [str(root / "render_pipeline.sh"), str(config_path)],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Unsupported render backend: vulkan", completed.stdout)
            self.assertFalse(marker.exists())

    def test_pipeline_dispatches_composite_from_frozen_render_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scene_root = root / "scene_workspace"
            scene_root.mkdir()
            shutil.copy2(Path("render_pipeline.sh"), root / "render_pipeline.sh")
            shutil.copy2(Path("render_snapshot.py"), root / "render_snapshot.py")
            composite = root / "render_shaft_composite.py"
            composite.write_text(
                "import json, os, sys\n"
                "with open(sys.argv[1]) as handle: config = json.load(handle)\n"
                "print('COMPOSITE_DISPATCH=' + "
                "str(config['render_settings']['shaft_composite']['enabled']))\n"
                "print('FROZEN_CONFIG=' + sys.argv[1])\n"
                "print('SNAPSHOT_RUN=' + os.environ['PBRT_RENDER_SNAPSHOT_DIR'])\n",
                encoding="utf-8",
            )
            config = {
                "file_names": {
                    "pbrt_scene": "scene.pbrt",
                    "working_image": "working.png",
                    "archive_image": "{scene_name}_{timestamp}.png",
                },
                "file_paths": {
                    "scene_files": "scene_workspace/scene_files",
                    "local_archive": "Archive",
                    "remote_archive": "unused:",
                    "pbrt_executable": "/usr/bin/false",
                },
                "camera_settings": {},
                "render_settings": {
                    "backend": {"type": "cpu", "show_statistics": False},
                    "shaft_composite": {"enabled": True},
                },
                "scene": {"name": "Composite Dispatch"},
            }
            config_path = scene_root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            completed = subprocess.run(
                [str(root / "render_pipeline.sh"), str(config_path)],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn("COMPOSITE_DISPATCH=True", completed.stdout)
            self.assertIn("/repository/scene_workspace/config.json", completed.stdout)
            self.assertIn("SNAPSHOT_RUN=", completed.stdout)
            self.assertNotIn("Building scene:", completed.stdout)

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

            fake_rclone = root / "rclone"
            fake_rclone.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            fake_rclone.chmod(0o755)

            builder = scene_root / "build_scene.py"
            builder.write_text(
                "import json, os, sys, time\n"
                "config_path = sys.argv[1]\n"
                "with open(config_path) as handle: config = json.load(handle)\n"
                "time.sleep(0.2)\n"
                "root = os.path.dirname(os.path.dirname(config_path))\n"
                "path = os.path.join(root, config['file_paths']['scene_files'], "
                "config['file_names']['pbrt_scene'])\n"
                "os.makedirs(os.path.dirname(path), exist_ok=True)\n"
                "with open(path, 'w') as handle: "
                "handle.write('# SCENE: ' + config['scene']['name'] + '\\nWorldBegin\\n')\n",
                encoding="utf-8",
            )

            config_path = scene_root / "config.json"
            config = {
                "file_names": {
                    "pbrt_scene": "scene.pbrt",
                    "working_image": "working.png",
                    "archive_image": "proof-{scene_name}-{timestamp}.png",
                },
                "file_paths": {
                    "scene_files": "generated/scenes",
                    "local_archive": "SavedRenders",
                    "remote_archive": "unused:",
                    "pbrt_executable": str(fake_pbrt),
                },
                "camera_settings": {
                    "enabled": True,
                    "type": "perspective",
                    "look_at": {
                        "eye": [0, 1, 2],
                        "look": [0, 0, 0],
                        "up": [0, 1, 0],
                    },
                    "fov": 50.0,
                },
                "render_settings": {
                    "film": {"x_resolution": 100, "y_resolution": 100},
                    "sampler": {"type": "halton", "pixel_samples": 4},
                    "integrator": {"type": "volpath", "max_depth": 8},
                    "backend": {"type": "cpu", "show_statistics": False},
                    "shaft_composite": {
                        "enabled": False,
                        "shaft_light": "shaft_sun",
                        "base_opacity": 1.0,
                        "shaft_opacity": 0.4,
                        "surface_reflectance_scale": 0.08,
                        "terrain_reflectance_scale": 0.015,
                        "blur_radius": 2.0,
                    },
                },
                "scene": {
                    "name": "Original Scene",
                    "trees": [],
                },
            }
            config_path.write_text(json.dumps(config), encoding="utf-8")

            environment = os.environ.copy()
            environment["PATH"] = f"{root}{os.pathsep}{environment['PATH']}"
            process = subprocess.Popen(
                [str(root / "render_pipeline.sh"), str(config_path)],
                cwd=root,
                env=environment,
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
            archived_configs = list(
                (root / "SavedRenders").glob(
                    "proof-Original_Scene-*_config.json"
                )
            )
            self.assertEqual(len(archived_configs), 1)
            archived_config = json.loads(archived_configs[0].read_text(encoding="utf-8"))
            self.assertEqual(archived_config["scene"]["name"], "Original Scene")
            archived_scenes = list(
                (root / "SavedRenders").glob("proof-Original_Scene-*.pbrt")
            )
            self.assertEqual(len(archived_scenes), 1)
            self.assertIn("# SCENE: Original Scene", archived_scenes[0].read_text())
            source_archives = list(
                (root / "SavedRenders").glob(
                    "proof-Original_Scene-*_snapshot_sources.tar.gz"
                )
            )
            self.assertEqual(len(source_archives), 1)
            with tarfile.open(source_archives[0], "r:gz") as archive:
                archived_names = archive.getnames()
            self.assertFalse(
                any(
                    name == "repository/generated/scenes"
                    or name.startswith("repository/generated/scenes/")
                    for name in archived_names
                )
            )
            self.assertEqual(
                list((scene_root / ".render_runs").iterdir()),
                [],
            )


@unittest.skipIf(
    render_shaft_composite is None,
    "shaft-composite NumPy/Pillow dependencies are unavailable",
)
class ShaftCompositeSnapshotTests(unittest.TestCase):
    def test_composite_uses_migrated_backend_settings(self):
        settings = {
            "backend": {"type": "gpu", "show_statistics": True}
        }
        self.assertEqual(
            render_shaft_composite.pbrt_flags(settings),
            ["--gpu", "--stats"],
        )
        settings["backend"]["type"] = "cpu"
        self.assertEqual(render_shaft_composite.pbrt_flags(settings), ["--stats"])
        settings["backend"]["type"] = "vulkan"
        with self.assertRaisesRegex(ValueError, "unsupported render backend"):
            render_shaft_composite.pbrt_flags(settings)

        settings["backend"]["type"] = "cpu"
        settings["backend"]["show_statistics"] = 1
        with self.assertRaisesRegex(ValueError, "show_statistics must be boolean"):
            render_shaft_composite.pbrt_flags(settings)

    def test_composite_options_require_valid_light_and_nonnegative_values(self):
        scene = {"lights": [{"label": "shaft_sun"}]}
        options = {
            "enabled": True,
            "shaft_light": "shaft_sun",
            "base_opacity": 1.0,
            "shaft_opacity": 0.4,
            "surface_reflectance_scale": 0.08,
            "terrain_reflectance_scale": 0.015,
            "blur_radius": 2.0,
        }
        render_shaft_composite.validate_composite_options(options, scene)

        options["shaft_light"] = "missing"
        with self.assertRaisesRegex(ValueError, "must resolve to a scene light"):
            render_shaft_composite.validate_composite_options(options, scene)

        options["shaft_light"] = "shaft_sun"
        options["blur_radius"] = -1.0
        with self.assertRaisesRegex(ValueError, "blur_radius must be nonnegative"):
            render_shaft_composite.validate_composite_options(options, scene)

    def test_composite_passes_use_migrated_scene_filenames(self):
        config = {
            "file_names": {"pbrt_scene": "scene.pbrt"},
            "scene": {
                "sun_aperture": {"enabled": True},
                "lights": [{"label": "shaft_sun", "enabled": True}],
                "landscape": {"ground": {}},
            },
        }
        base = render_shaft_composite.configure_base(config, "shaft_sun")
        shaft = render_shaft_composite.configure_shaft(
            config, "shaft_sun", 0.0, 0.0
        )
        self.assertEqual(base["file_names"]["pbrt_scene"], "scene_base.pbrt")
        self.assertEqual(shaft["file_names"]["pbrt_scene"], "scene_shaft.pbrt")
        self.assertNotIn("master_file", base["scene"])
        self.assertNotIn("master_file", shaft["scene"])

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
