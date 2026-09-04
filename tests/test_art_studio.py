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

    def test_render_page_exposes_migrated_file_names_and_paths(self):
        expected = {
            "pbrt_scene_filename": "scene.pbrt",
            "working_image_filename": "working_scene.png",
            "archive_image_pattern": "{scene_name}_{timestamp}.png",
            "scene_files_path": "scene_workspace/scene_files",
            "local_archive_path": "Archive",
            "remote_archive_path": "gdrive:wipImages/pbrt-v4",
            "pbrt_executable_path": "/home/rpf4/pbrt-v4/build/pbrt",
        }
        for object_name, value in expected.items():
            widget = self.window.findChild(QtWidgets.QLineEdit, object_name)
            self.assertIsNotNone(widget, object_name)
            self.assertEqual(widget.text(), value)

    def test_camera_page_uses_root_camera_settings(self):
        enabled = self.window.findChild(QtWidgets.QCheckBox, "camera_enabled")
        camera_type = self.window.findChild(QtWidgets.QComboBox, "camera_type")
        self.assertIsNotNone(enabled)
        self.assertTrue(enabled.isChecked())
        self.assertIsNotNone(camera_type)
        self.assertEqual(camera_type.currentData(), "perspective")

        self.window.inspector._set(("camera_settings", "fov"), 47.5)
        self.assertTrue(self.window.save_config())
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(data["camera_settings"]["fov"], 47.5)
        self.assertNotIn("camera", data["scene"])

    def test_render_page_uses_root_render_settings(self):
        sampler = self.window.findChild(
            QtWidgets.QComboBox, "render_sampler_type"
        )
        integrator = self.window.findChild(
            QtWidgets.QComboBox, "render_integrator_type"
        )
        backend = self.window.findChild(
            QtWidgets.QComboBox, "render_backend_type"
        )
        statistics = self.window.findChild(
            QtWidgets.QCheckBox, "render_show_statistics"
        )
        shaft = self.window.findChild(
            QtWidgets.QCheckBox, "shaft_composite_enabled"
        )
        self.assertEqual(sampler.currentData(), "halton")
        self.assertEqual(integrator.currentData(), "volpath")
        self.assertEqual(backend.currentData(), "gpu")
        self.assertTrue(statistics.isChecked())
        self.assertFalse(shaft.isChecked())

        backend.setCurrentIndex(backend.findData("cpu"))
        self.application.processEvents()
        self.assertTrue(self.window.save_config())
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(data["render_settings"]["backend"]["type"], "cpu")
        self.assertNotIn("runtime", data)
        self.assertNotIn("pipeline", data)
        for obsolete in ("film", "sampler", "integrator"):
            self.assertNotIn(obsolete, data["scene"])

    def test_latest_render_uses_configured_local_archive(self):
        archive = Path(self.temporary_directory.name) / "ConfiguredArchive"
        archive.mkdir()
        image_path = archive / "configured_20260904_030000.png"
        image_path.write_bytes(b"diagnostic image")
        self.window.config.set(
            ("file_paths", "local_archive"), str(archive)
        )
        with mock.patch.object(self.window.image, "load", return_value=True) as load:
            self.window._load_latest_render()
        load.assert_called_once_with(image_path)

    def test_migrated_path_control_saves_authoritative_json(self):
        widget = self.window.findChild(
            QtWidgets.QLineEdit, "remote_archive_path"
        )
        self.assertIsNotNone(widget)
        widget.setText("gdrive:wipImages/pbrt-v4/path-control-test")
        widget.editingFinished.emit()
        self.assertTrue(self.window.save_config())
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(
            data["file_paths"]["remote_archive"],
            "gdrive:wipImages/pbrt-v4/path-control-test",
        )
        self.assertNotIn("archive", data)

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
