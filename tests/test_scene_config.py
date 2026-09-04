import json
from pathlib import Path
import tempfile
import unittest

from scene_config import SceneConfig, SceneConfigConflictError, SceneConfigError


class SceneConfigTests(unittest.TestCase):
    def make_config(self, directory):
        source = '''{
  "file_names": {
    "pbrt_scene": "scene.pbrt",
    "working_image": "working.png",
    "archive_image": "{scene_name}_{timestamp}.png"
  },
  "file_paths": {
    "scene_files": "scene_workspace/scene_files",
    "local_archive": "Archive",
    "remote_archive": "unused:",
    "pbrt_executable": "/usr/bin/false"
  },
  "camera_settings": {
    "enabled": true,
    "type": "perspective",
    "look_at": { "eye": [0, 1, 2], "look": [0, 0, 0], "up": [0, 1, 0] },
    "fov": 55.0
  },
  "scene": {
    "landscape": {
      "ground": {
        "active_landform": "flat",
        "landforms": { "flat": {}, "gully": {} },
        "details": {
          "grass": { "enabled": true, "layers": [{ "count": 10 }] },
          "poppies": {
            "enabled": true,
            "count": 20,
            "scale": [1.0, 2.0],
            "camera_frustum": {
              "enabled": true,
              "placement_reference": "flower"
            }
          }
        }
      },
      "water": { "enabled": false },
      "distant_hills": { "enabled": false }
    },
    "sky": {
      "background": { "enabled": true, "type": "infinite" },
      "clouds": { "enabled": false }
    },
    "film": { "x_resolution": 100, "y_resolution": 100 },
    "fog": { "enabled": false },
    "lsystem_trees": [],
    "trees": []
  }
}
'''
        path = Path(directory) / "config.json"
        path.write_text(source, encoding="utf-8")
        return path, source

    def test_targeted_save_preserves_surrounding_formatting(self):
        with tempfile.TemporaryDirectory() as directory:
            path, source = self.make_config(directory)
            config = SceneConfig(path)
            config.set("scene.landscape.ground.details.poppies.count", 2600)
            config.set("camera_settings.look_at.eye", [4, 5, 6])
            config.save()
            result = path.read_text(encoding="utf-8")
            expected = source.replace('"count": 20', '"count": 2600').replace(
                '"eye": [0, 1, 2]', '"eye": [4, 5, 6]'
            )
            self.assertEqual(result, expected)
            self.assertFalse(config.dirty)

    def test_external_edit_blocks_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            config = SceneConfig(path)
            config.set("scene.landscape.ground.details.poppies.count", 21)
            path.write_text(path.read_text() + "\n", encoding="utf-8")
            with self.assertRaises(SceneConfigConflictError):
                config.save()

    def test_invalid_value_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path, source = self.make_config(directory)
            config = SceneConfig(path)
            config.set(
                "scene.landscape.ground.details.poppies.scale",
                [5.0, 1.0],
            )
            with self.assertRaises(SceneConfigError):
                config.save()
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_invalid_poppy_framing_reference_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path, source = self.make_config(directory)
            config = SceneConfig(path)
            config.set(
                "scene.landscape.ground.details.poppies."
                "camera_frustum.placement_reference",
                "whole_plant",
            )
            with self.assertRaises(SceneConfigError):
                config.save()
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_invalid_camera_depth_fade_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path, source = self.make_config(directory)
            config = SceneConfig(path)
            config.set(
                "scene.landscape.ground.details.poppies.camera_frustum",
                {
                    "enabled": True,
                    "placement_reference": "flower",
                    "depth_fade": {
                        "enabled": True,
                        "start": 40.0,
                        "end": 20.0,
                        "minimum_density": 0.0,
                    },
                },
            )
            with self.assertRaises(SceneConfigError):
                config.save()
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_invalid_camera_geometry_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path, source = self.make_config(directory)
            config = SceneConfig(path)
            config.set("camera_settings.look_at.look", [0, 1, 2])
            with self.assertRaisesRegex(
                SceneConfigError, "camera_settings eye and look points must differ"
            ):
                config.save()
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_current_scene_is_valid_and_describable(self):
        root = Path(__file__).resolve().parents[1]
        config = SceneConfig(root / "scene_workspace" / "config.json")
        self.assertEqual(config.validate(), [])
        description = config.describe()
        self.assertIn("Landform: flat_landform", description)
        self.assertIn("Poppies:", description)
        self.assertIn("Water: disabled", description)
        enabled_layers = sum(
            layer.get("enabled", False)
            for layer in config.get(
                "scene.landscape.distant_hills.layers",
            )
        )
        hill_status = (
            "enabled"
            if config.get("scene.landscape.distant_hills.enabled")
            else "disabled"
        )
        self.assertIn(
            f"Distant hills: {hill_status}, {enabled_layers} "
            f"{'layer' if enabled_layers == 1 else 'layers'}",
            description,
        )
        self.assertIn("Sky background: enabled", description)
        self.assertIn("Clouds: enabled", description)

    def test_current_scene_uses_explicit_landscape_and_sky_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (root / "scene_workspace" / "config.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            list(config)[:3],
            ["file_names", "file_paths", "camera_settings"],
        )
        self.assertNotIn("archive", config)
        self.assertNotIn("pbrt_binary", config["runtime"])
        self.assertNotIn("rclone_sync", config["pipeline"])
        data = config["scene"]
        self.assertNotIn("camera", data)
        for obsolete in ("master_file", "output_filename", "generated_medium"):
            self.assertNotIn(obsolete, data)
        self.assertNotIn("terrain", data)
        self.assertEqual(
            set(data["landscape"]),
            {"ground", "water", "distant_hills"},
        )
        self.assertEqual(set(data["sky"]), {"background", "clouds"})
        self.assertEqual(data["sky"]["background"]["type"], "infinite")
        self.assertTrue(all(light.get("type") != "infinite" for light in data["lights"]))

    def test_invalid_stage_one_paths_are_reported_at_new_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["file_names"]["archive_image"] = "render.png"
            data["file_paths"]["scene_files"] = "../outside"
            data["file_paths"]["pbrt_executable"] = "relative/pbrt"
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = SceneConfig(path).validate()
            self.assertIn(
                "file_names.archive_image must contain {scene_name} and {timestamp}",
                errors,
            )
            self.assertIn(
                "file_paths.scene_files must be a repository-relative path",
                errors,
            )
            self.assertIn(
                "file_paths.pbrt_executable must be an absolute path",
                errors,
            )

    def test_invalid_stage_one_filenames_and_placeholders_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["file_names"]["working_image"] = ".."
            data["file_names"]["archive_image"] = (
                "{scene_name}_{timestamp}_{unsupported}.PNG"
            )
            data["file_paths"]["scene_files"] = "."
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = SceneConfig(path).validate()
            self.assertIn(
                "file_names.working_image must be a filename without a directory",
                errors,
            )
            self.assertIn(
                "file_names.archive_image contains an unsupported placeholder",
                errors,
            )
            self.assertIn(
                "file_names.archive_image must be a PNG filename",
                errors,
            )
            self.assertIn(
                "file_paths.scene_files must be a repository-relative path",
                errors,
            )

    def test_saved_json_remains_parseable(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            config = SceneConfig(path)
            config.set("scene.landscape.ground.active_landform", "gully")
            config.save()
            self.assertEqual(
                json.loads(path.read_text())["scene"]["landscape"]["ground"][
                    "active_landform"
                ],
                "gully",
            )


if __name__ == "__main__":
    unittest.main()
