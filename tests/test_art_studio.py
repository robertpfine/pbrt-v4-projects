import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtGui, QtWidgets

from pbrt_v4_art_studio import (
    SceneSetupDialog,
    StudioWindow,
    scene_components,
    visible_components,
)
from scene_config import SceneConfig


class ArtStudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        cls.root = Path(__file__).resolve().parents[1]

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temporary_directory.name) / "config.json"
        # Tests run against a frozen canonical scene, never the artist's live
        # scene_workspace/config.json, so saving or rendering from the Studio
        # cannot turn tests red.
        shutil.copy2(
            self.root / "tests" / "fixtures" / "canonical_config.json",
            self.config_path,
        )
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
                "objects",
                "sky",
                "clouds",
                "atmosphere",
                "lighting",
                "camera",
                "render",
            },
        )

    def test_scene_page_uses_scene_description_and_context(self):
        mode = self.window.findChild(
            QtWidgets.QComboBox, "scene_description_mode"
        )
        expected_text = {
            "scene_description_name": "Poppy Field Overcast 8AM Study",
            "scene_context_date": "2026-06-21",
            "scene_context_local_time": "08:00:00",
            "scene_context_time_zone": "America/New_York",
        }
        self.assertIsNotNone(mode)
        self.assertEqual(mode.currentData(), "new")
        for object_name, value in expected_text.items():
            widget = self.window.findChild(QtWidgets.QLineEdit, object_name)
            self.assertIsNotNone(widget, object_name)
            self.assertEqual(widget.text(), value)

        self.window.inspector._set(("scene_description", "name"), "Context Study")
        self.window.inspector._set(
            ("scene_description", "scene_context", "longitude"), -75.5
        )
        self.assertTrue(self.window.save_config())
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(data["scene_description"]["name"], "Context Study")
        self.assertEqual(
            data["scene_description"]["scene_context"]["longitude"], -75.5
        )
        self.assertNotIn("scene", data)

    def test_control_change_saves_to_the_single_configuration(self):
        path = (
            "scene_description",
            "landforms",
            1,
            "surface_objects",
            1,
            "population",
            "count",
        )
        self.window.inspector._set(path, 2700)
        self.assertTrue(self.window.config.dirty)
        self.assertTrue(self.window.save_config())
        result = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(
            result["scene_description"]["landforms"][1]["surface_objects"][1][
                "population"
            ]["count"],
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
                "scene_description.landforms.1.surface_objects.1.population."
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

    def test_independent_object_page_exposes_planar_phyllotaxis(self):
        self.window.inspector.show_page("objects")
        selector = self.window.inspector.pages["objects"].findChild(
            QtWidgets.QComboBox
        )
        self.assertIsNotNone(selector)
        self.assertEqual(selector.currentText(), "sunflower_head_vogel_pattern")
        self.assertEqual(
            [selector.itemText(index) for index in range(selector.count())],
            ["sunflower_head_vogel_pattern", "volume_sphere", "volume_box"],
        )

    def test_no_add_control_is_present(self):
        buttons = self.window.findChildren(QtWidgets.QAbstractButton)
        self.assertNotIn("Add", {button.text() for button in buttons})

    def test_outline_mirrors_config_roots_and_shows_enabled_components_only(self):
        self.assertEqual(self.window.navigation.headerItem().text(0), "OUTLINE")
        keys = self.window.outline_keys()
        self.assertEqual(keys[:3], ["setup", "camera", "render"])
        self.assertIn("scene_root", keys)
        self.assertIn("scene", keys)
        # Enabled landforms and the one enabled surface object appear ...
        self.assertIn("landform:1", keys)  # flat_landform
        self.assertIn("landform:2", keys)  # vista_plane
        self.assertIn("landform:1:so:6", keys)  # fractal_tree
        # ... disabled ones do not, and nothing is dimmed in their place.
        self.assertNotIn("landform:0", keys)  # right_dip_rise
        self.assertNotIn("landform:3", keys)  # broad_rise
        self.assertNotIn("landform:1:so:0", keys)  # grass
        # Grouping rows with nothing enabled under them are omitted.
        self.assertNotIn("clouds", keys)
        self.assertNotIn("objects", keys)
        self.assertNotIn("atmosphere", keys)
        self.assertNotIn("water", keys)
        self.assertIn("sky", keys)
        self.assertIn("lighting", keys)

    def test_outline_rows_open_existing_pages(self):
        pages = {
            component.key: component.page
            for component in scene_components(self.window.config)
            if not component.heading
        }
        self.assertEqual(pages["landform:1"], "landform")
        self.assertEqual(pages["landform:3"], "distant_hills")
        self.assertEqual(pages["landform:1:so:0"], "grass")
        self.assertEqual(pages["landform:1:so:1"], "poppies")
        self.assertEqual(pages["landform:1:so:6"], "trees")
        self.assertEqual(pages["landform:1:texture"], "ground")
        self.assertEqual(pages["cloud:0"], "clouds")
        self.assertEqual(pages["atmosphere:fog:0"], "atmosphere")
        for page in set(pages.values()):
            self.assertIn(page, self.window.inspector.pages)

    def test_scene_setup_checkbox_enables_component_and_refreshes_outline(self):
        dialog = SceneSetupDialog(self.window.config, self.window, launch=False)
        grass = dialog.findChild(QtWidgets.QCheckBox, "component:landform:1:so:0")
        clouds = dialog.findChild(QtWidgets.QCheckBox, "component:cloud:2")
        self.assertIsNotNone(grass)
        self.assertIsNotNone(clouds)
        self.assertFalse(grass.isChecked())
        grass.setChecked(True)
        clouds.setChecked(True)
        self.application.processEvents()
        self.assertTrue(self.window.config.get(
            ("scene_description", "landforms", 1, "surface_objects", 0, "enabled")
        ))
        self.assertTrue(self.window.config.dirty)
        self.window._refresh_navigation()
        keys = self.window.outline_keys()
        self.assertIn("landform:1:so:0", keys)
        self.assertIn("clouds", keys)
        self.assertIn("cloud:2", keys)
        self.assertNotIn("cloud:0", keys)
        dialog.close()

    def test_scene_setup_keeps_exactly_one_terrain_heightfield_landform(self):
        dialog = SceneSetupDialog(self.window.config, self.window, launch=False)
        dip_rise = dialog.findChild(QtWidgets.QCheckBox, "component:landform:0")
        flat = dialog.findChild(QtWidgets.QCheckBox, "component:landform:1")
        vista = dialog.findChild(QtWidgets.QCheckBox, "component:landform:2")
        self.assertTrue(flat.isChecked())
        self.assertFalse(dip_rise.isChecked())
        dip_rise.setChecked(True)
        self.application.processEvents()
        self.assertTrue(dip_rise.isChecked())
        self.assertFalse(flat.isChecked())
        self.assertTrue(vista.isChecked())  # not a heightfield: independent
        self.assertTrue(self.window.config.get(
            ("scene_description", "landforms", 0, "enabled")
        ))
        self.assertFalse(self.window.config.get(
            ("scene_description", "landforms", 1, "enabled")
        ))
        self.assertEqual(self.window.config.terrain_landform_index(), 0)
        dialog.close()

    def test_scene_setup_exposes_camera_and_render_controls(self):
        dialog = SceneSetupDialog(self.window.config, self.window, launch=True)
        name = dialog.findChild(QtWidgets.QLineEdit, "setup_scene_name")
        backend = dialog.findChild(QtWidgets.QComboBox, "setup_backend")
        self.assertEqual(name.text(), "Poppy Field Overcast 8AM Study")
        self.assertEqual(backend.currentData(), "gpu")
        self.assertIsNotNone(dialog.findChild(QtWidgets.QPushButton, "setup_open"))
        self.assertIsNotNone(dialog.findChild(QtWidgets.QPushButton, "setup_quit"))
        # Paths and file names are governed by convention, not the dialog.
        self.assertIsNone(dialog.findChild(QtWidgets.QLineEdit, "remote_archive_path"))
        dialog.close()

    def test_window_accepts_a_preloaded_scene_config(self):
        config = SceneConfig(self.config_path)
        config.set(("scene_description", "landforms", 3, "enabled"), True)  # broad_rise
        window = StudioWindow(config)
        try:
            self.assertIs(window.config, config)
            self.assertIn("landform:3", window.outline_keys())
        finally:
            # Discard the unsaved toggle so closeEvent does not open the
            # modal "Save the scene before closing?" prompt offscreen.
            config.reload()
            window.close()

    def test_refresh_image_loads_newest_archive_render_on_demand(self):
        archive = Path(self.temporary_directory.name) / "RefreshArchive"
        archive.mkdir()
        older = archive / "scene_20260907_010000.png"
        newer = archive / "scene_20260907_020000.png"
        older.write_bytes(b"older")
        newer.write_bytes(b"newer")
        os.utime(older, (1, 1))
        self.window.config.set(("file_paths", "local_archive"), str(archive))
        action = next(
            a for a in self.window.findChildren(QtGui.QAction)
            if a.objectName() == "refresh_image_action"
        )
        with mock.patch.object(self.window.image, "load", return_value=True) as load:
            action.trigger()
        load.assert_called_once_with(newer)
        self.assertIn("Displayed scene_20260907_020000.png", self.window.status_label.text())

    def test_scene_setup_toolbar_action_is_present(self):
        actions = {action.text() for action in self.window.findChildren(QtGui.QAction)}
        self.assertIn("Scene Setup…", actions)

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
        self.assertNotIn("scene", data)

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
        self.assertNotIn("scene", data)

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
