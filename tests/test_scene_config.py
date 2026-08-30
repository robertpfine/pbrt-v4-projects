import json
from pathlib import Path
import tempfile
import unittest

from scene_config import SceneConfig, SceneConfigConflictError, SceneConfigError


class SceneConfigTests(unittest.TestCase):
    def make_config(self, directory):
        source = '''{
  "scene": {
    "terrain": {
      "active_landform": "flat",
      "landforms": { "flat": {}, "gully": {} },
      "details": {
        "grass": { "enabled": true, "layers": [{ "count": 10 }] },
        "poppies": {
          "enabled": true,
          "count": 20,
          "scale": [1.0, 2.0],
          "camera_frustum": { "enabled": true, "frame_margin": 0.02 }
        }
      }
    },
    "camera": {
      "look_at": { "eye": [0, 1, 2], "look": [0, 0, 0], "up": [0, 1, 0] },
      "fov": 55.0
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
            config.set("scene.terrain.details.poppies.count", 2600)
            config.set("scene.camera.look_at.eye", [4, 5, 6])
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
            config.set("scene.terrain.details.poppies.count", 21)
            path.write_text(path.read_text() + "\n", encoding="utf-8")
            with self.assertRaises(SceneConfigConflictError):
                config.save()

    def test_invalid_value_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path, source = self.make_config(directory)
            config = SceneConfig(path)
            config.set("scene.terrain.details.poppies.scale", [5.0, 1.0])
            with self.assertRaises(SceneConfigError):
                config.save()
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_current_scene_is_valid_and_describable(self):
        root = Path(__file__).resolve().parents[1]
        config = SceneConfig(root / "scene_workspace" / "config.json")
        self.assertEqual(config.validate(), [])
        description = config.describe()
        self.assertIn("Landform: flat_landform", description)
        self.assertIn("Poppies:", description)

    def test_saved_json_remains_parseable(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            config = SceneConfig(path)
            config.set("scene.terrain.active_landform", "gully")
            config.save()
            self.assertEqual(json.loads(path.read_text())["scene"]["terrain"]["active_landform"], "gully")


if __name__ == "__main__":
    unittest.main()
