import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from pbrt_v4_art_studio import StudioWindow


class ArtStudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        cls.root = Path(__file__).resolve().parents[1]

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temporary_directory.name) / "config.json"
        shutil.copy2(self.root / "scene_workspace" / "config.json", self.config_path)
        self.window = StudioWindow(self.config_path)
        self.window.show()
        self.application.processEvents()

    def tearDown(self):
        if self.window.config.dirty:
            self.window.config.reload()
        self.window.close()
        self.temporary_directory.cleanup()

    def test_application_uses_artist_approved_name_and_categories(self):
        self.assertEqual(self.window.windowTitle(), "PBRT-v4 Art Studio")
        self.assertEqual(
            set(self.window.inspector.pages),
            {
                "scene",
                "composition",
                "landscape",
                "ground",
                "landform",
                "grass",
                "poppies",
                "trees",
                "distant_hills",
                "sky",
                "clouds",
                "atmosphere",
                "lighting",
                "camera",
                "render",
            },
        )

    def test_control_change_saves_to_the_single_configuration(self):
        path = ("scene", "terrain", "details", "poppies", "count")
        self.window.inspector._set(path, 2700)
        self.assertTrue(self.window.config.dirty)
        self.assertTrue(self.window.save_config())
        result = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(result["scene"]["terrain"]["details"]["poppies"]["count"], 2700)
        self.assertNotIn("project", result)

    def test_no_add_control_is_present(self):
        buttons = self.window.findChildren(QtWidgets.QAbstractButton)
        self.assertNotIn("Add", {button.text() for button in buttons})

    def test_carriage_return_progress_reuses_one_live_line(self):
        before = self.window.log.blockCount()
        self.window._feed_render_output("Rendering [++++      ]\r")
        self.window._feed_render_output("Rendering [++++++++  ]\r")
        self.assertEqual(
            self.window.progress_line.text(),
            "Rendering [++++++++  ]",
        )
        self.assertEqual(self.window.log.blockCount(), before)
        self.window._feed_render_output("Rendering complete\n")
        self.assertEqual(self.window.progress_line.text(), "")
        self.assertIn("Rendering complete", self.window.log.toPlainText())


if __name__ == "__main__":
    unittest.main()
