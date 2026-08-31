import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


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
                "water",
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
        path = (
            "scene", "landscape", "ground", "details", "poppies", "count"
        )
        self.window.inspector._set(path, 2700)
        self.assertTrue(self.window.config.dirty)
        self.assertTrue(self.window.save_config())
        result = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(
            result["scene"]["landscape"]["ground"]["details"]["poppies"][
                "count"
            ],
            2700,
        )
        self.assertNotIn("project", result)

    def test_poppy_placement_reference_switch_updates_config(self):
        selector = self.window.findChild(
            QtWidgets.QComboBox,
            "poppy_placement_reference",
        )
        self.assertIsNotNone(selector)
        self.assertEqual(selector.currentData(), "flower")
        selector.setCurrentIndex(selector.findData("root"))
        self.application.processEvents()
        self.assertEqual(
            self.window.config.get(
                "scene.landscape.ground.details.poppies."
                "camera_frustum.placement_reference"
            ),
            "root",
        )

    def test_distant_hill_controls_expose_the_single_broad_rise(self):
        layer_selector = self.window.findChild(
            QtWidgets.QComboBox,
            "distant_hill_layer",
        )
        peak_selector = self.window.findChild(
            QtWidgets.QComboBox,
            "distant_hill_peak",
        )
        self.assertIsNotNone(layer_selector)
        self.assertIsNotNone(peak_selector)
        self.application.processEvents()
        self.assertEqual(layer_selector.count(), 1)
        self.assertEqual(layer_selector.currentText(), "broad_rise")
        self.assertEqual(peak_selector.count(), 1)
        self.assertEqual(peak_selector.currentText(), "Peak 1")

    def test_no_add_control_is_present(self):
        buttons = self.window.findChildren(QtWidgets.QAbstractButton)
        self.assertNotIn("Add", {button.text() for button in buttons})

    def test_carriage_return_progress_is_recorded_line_by_line(self):
        before = self.window.log.blockCount()
        self.window._feed_render_output("Rendering [++++      ]\r")
        self.window._feed_render_output("Rendering [++++++++  ]\r")
        self.assertEqual(self.window.log.blockCount(), before + 2)
        self.assertIn("Rendering [++++      ]", self.window.log.toPlainText())
        self.assertIn("Rendering [++++++++  ]", self.window.log.toPlainText())
        self.window._feed_render_output("Rendering complete\n")
        self.assertIn("Rendering complete", self.window.log.toPlainText())

    def test_newline_progress_is_recorded_line_by_line(self):
        before = self.window.log.blockCount()
        self.window._feed_render_output("Rendering: [++++      ]\n")
        self.window._feed_render_output("Rendering: [++++++++  ]\n")
        self.assertEqual(self.window.log.blockCount(), before + 2)
        self.assertIn("Rendering: [++++      ]", self.window.log.toPlainText())
        self.assertIn("Rendering: [++++++++  ]", self.window.log.toPlainText())

    def test_local_render_marker_updates_image_before_sync_finishes(self):
        image_path = Path(self.temporary_directory.name) / "finished.png"
        with mock.patch.object(self.window.image, "load", return_value=True) as load:
            self.window._feed_render_output(
                f"ART_STUDIO_RENDER_READY={image_path}\n"
            )
        load.assert_called_once_with(image_path)
        self.assertIn("Displayed local render", self.window.log.toPlainText())
        self.assertIn("archive/sync continuing", self.window.status_label.text())


if __name__ == "__main__":
    unittest.main()
