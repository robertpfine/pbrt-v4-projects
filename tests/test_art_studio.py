import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets

from pbrt_v4_art_studio import (
    SceneSetupDialog,
    StudioWindow,
    entry_page_key,
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

    def test_every_page_is_an_entry_page_built_from_config(self):
        self.assertEqual(self.window.windowTitle(), "PBRT-v4 Art Studio")
        expected = {"setup_scene"} | {
            component.page
            for component in scene_components(self.window.config)
            if component.path is not None
        }
        self.assertEqual(set(self.window.inspector.pages), expected)
        # 4 landforms + 9 land cover + 3 objects + 4 clouds + background + sun
        # + fog + rain + water + camera + render = 27 entries, plus Setup > Scene.
        self.assertEqual(len(expected), 28)
        # Nothing routes to the retired curated pages or to "Context".
        for legacy in ("scene", "context", "ground", "grass", "poppies", "trees",
                       "distant_hills", "clouds", "lighting", "composition"):
            self.assertNotIn(legacy, self.window.inspector.pages)

    def test_setup_scene_page_shows_name_and_date_only(self):
        page = self.window.inspector.pages["setup_scene"]
        name = page.findChild(QtWidgets.QLineEdit, "field:scene_description.name")
        date = page.findChild(
            QtWidgets.QLineEdit, "field:scene_description.scene_context.date"
        )
        self.assertEqual(name.text(), "Poppy Field Overcast 8AM Study")
        self.assertEqual(date.text(), "2026-06-21")
        # Mode, latitude, longitude, time zone, world north are not shown.
        self.assertEqual(len(page.findChildren(QtWidgets.QLineEdit)), 2)
        for absent in ("mode", "latitude", "longitude", "time_zone", "world_north"):
            self.assertIsNone(
                self.window.findChild(QtWidgets.QWidget, f"field:scene_description.scene_context.{absent}"),
                absent,
            )
        self.assertIsNone(self.window.findChild(QtWidgets.QWidget, "field:scene_description.mode"))
        name.setText("Setup Study")
        name.editingFinished.emit()
        self.assertTrue(self.window.save_config())
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(data["scene_description"]["name"], "Setup Study")
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

    def test_poppy_placement_reference_is_plain_text_and_writes_back(self):
        path = ("scene_description", "landforms", 1, "surface_objects", 1)
        page = self.window.inspector.pages[entry_page_key(path)]
        field = page.findChild(
            QtWidgets.QLineEdit,
            "field:" + ".".join(str(p) for p in path)
            + ".population.camera_frustum.placement_reference",
        )
        self.assertIsNotNone(field)
        self.assertEqual(field.text(), "flower")
        field.setText("root")
        field.editingFinished.emit()
        self.assertEqual(
            self.window.config.get(path + ("population", "camera_frustum", "placement_reference")),
            "root",
        )

    def test_landform_page_shows_the_whole_landform_except_land_cover(self):
        path = ("scene_description", "landforms", 1)  # flat_landform
        page = self.window.inspector.pages[entry_page_key(path)]
        sections = [g.title() for g in page.findChildren(QtWidgets.QGroupBox)]
        for top in ("PLACEMENT", "GEOMETRY", "TOPOGRAPHY", "SURFACE"):
            self.assertIn(top, sections)
        self.assertIn("patches", sections)
        self.assertIn("noise", sections)
        self.assertIn("texture", sections)
        self.assertNotIn("SURFACE_OBJECTS", sections)  # presented as land cover
        seed = page.findChild(
            QtWidgets.QSpinBox,
            "field:scene_description.landforms.1.surface.texture.terrain_surface_texture.seed",
        )
        self.assertEqual(seed.value(), 97)
        # broad_rise gets the same treatment, not a special page.
        ridge = self.window.inspector.pages[entry_page_key(("scene_description", "landforms", 3))]
        generator = ridge.findChild(
            QtWidgets.QLineEdit, "field:scene_description.landforms.3.topography.generator"
        )
        self.assertEqual(generator.text(), "distant_ridge")

    def test_each_independent_object_has_its_own_entry_page(self):
        for index, name in enumerate(
            ["sunflower_head_vogel_pattern", "volume_sphere", "volume_box"]
        ):
            path = ("scene_description", "objects", index)
            page = self.window.inspector.pages[entry_page_key(path)]
            field = page.findChild(
                QtWidgets.QLineEdit, "field:scene_description.objects.%d.name" % index
            )
            self.assertEqual(field.text(), name)

    def test_no_add_control_is_present(self):
        buttons = self.window.findChildren(QtWidgets.QAbstractButton)
        self.assertNotIn("Add", {button.text() for button in buttons})

    def test_outline_mirrors_config_roots_and_shows_enabled_components_only(self):
        self.assertEqual(self.window.navigation.headerItem().text(0), "OUTLINE")
        keys = self.window.outline_keys()
        self.assertEqual(keys[:4], ["setup", "setup_scene", "camera", "render"])
        self.assertIn("scene_root", keys)
        self.assertNotIn("scene", keys)  # "Context" is gone
        # Enabled landforms and the one enabled land-cover entry appear ...
        self.assertIn("landform:1", keys)  # flat_landform
        self.assertIn("landform:2", keys)  # vista_plane
        self.assertIn("land_cover", keys)
        self.assertIn("cover:1:6", keys)  # fractal_tree, on flat_landform
        # ... land cover is its own collection, not nested under landforms ...
        self.assertLess(keys.index("landform:2"), keys.index("land_cover"))
        self.assertLess(keys.index("land_cover"), keys.index("cover:1:6"))
        # ... the texture row is gone (texture is on the landform's page) ...
        self.assertNotIn("landform:1:texture", keys)
        # ... containers only expand/collapse ...
        for key in ("setup", "scene_root", "landforms", "land_cover", "sky_root"):
            self.assertFalse(self._outline_item(key).flags() & QtCore.Qt.ItemFlag.ItemIsSelectable, key)
        self.assertTrue(self._outline_item("landform:1").flags() & QtCore.Qt.ItemFlag.ItemIsSelectable)
        # ... disabled ones do not, and nothing is dimmed in their place.
        self.assertNotIn("landform:0", keys)  # right_dip_rise
        self.assertNotIn("landform:3", keys)  # broad_rise
        self.assertNotIn("cover:1:0", keys)  # grass
        # Grouping rows with nothing enabled under them are omitted.
        self.assertNotIn("clouds", keys)
        self.assertNotIn("objects", keys)
        self.assertNotIn("atmosphere", keys)
        self.assertNotIn("water", keys)
        self.assertIn("sky", keys)
        self.assertIn("lighting", keys)

    def _outline_item(self, key):
        def walk(item):
            if item.data(0, QtCore.Qt.ItemDataRole.UserRole) == key:
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None
        for index in range(self.window.navigation.topLevelItemCount()):
            found = walk(self.window.navigation.topLevelItem(index))
            if found is not None:
                return found
        self.fail(f"Outline row {key!r} not found")

    def test_clicking_a_container_row_does_not_change_the_page(self):
        camera_page = self.window.inspector.pages[entry_page_key(("camera_settings",))]
        self.window.navigation.setCurrentItem(self._outline_item("camera"))
        self.application.processEvents()
        self.assertIs(self.window.inspector.stack.currentWidget(), camera_page)
        for key in ("sky_root", "landforms", "land_cover", "scene_root", "setup"):
            self.window.navigation.setCurrentItem(self._outline_item(key))
            self.application.processEvents()
            self.assertIs(self.window.inspector.stack.currentWidget(), camera_page, key)

    def test_every_outline_row_opens_its_own_entry_page(self):
        components = scene_components(self.window.config)
        pages = {c.key: c.page for c in components if not c.heading}
        self.assertEqual(pages["landform:1"], entry_page_key(("scene_description", "landforms", 1)))
        self.assertEqual(pages["landform:3"], entry_page_key(("scene_description", "landforms", 3)))
        for j in range(9):  # every land-cover entry, litter and rocks included
            self.assertEqual(
                pages[f"cover:1:{j}"],
                entry_page_key(("scene_description", "landforms", 1, "surface_objects", j)),
            )
        self.assertEqual(pages["cloud:0"], entry_page_key(("scene_description", "sky", "clouds", 0)))
        self.assertEqual(pages["atmosphere:fog:0"], entry_page_key(("scene_description", "atmosphere", "fog", 0)))
        self.assertEqual(pages["water"], entry_page_key(("scene_description", "water")))
        self.assertEqual(pages["camera"], entry_page_key(("camera_settings",)))
        self.assertEqual(pages["render"], entry_page_key(("render_settings",)))
        for page in set(pages.values()):
            self.assertIn(page, self.window.inspector.pages)
        # Containers have no page at all.
        self.assertEqual({c.page for c in components if c.heading}, {""})

    def test_scene_setup_checkbox_enables_component_and_refreshes_outline(self):
        dialog = SceneSetupDialog(self.window.config, self.window, launch=False)
        grass = dialog.findChild(QtWidgets.QCheckBox, "component:cover:1:0")
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
        self.assertIn("cover:1:0", keys)
        self.assertIn("clouds", keys)
        self.assertIn("cloud:2", keys)
        self.assertNotIn("cloud:0", keys)
        dialog.close()

    def test_scene_setup_presents_land_cover_as_a_mapping(self):
        dialog = SceneSetupDialog(self.window.config, self.window, launch=False)
        labels = [
            label.text() for label in dialog.findChildren(QtWidgets.QLabel)
        ]
        self.assertIn("LAND COVER", labels)
        self.assertIn("WATER", labels)
        self.assertTrue(any("mapping" in text for text in labels))
        # The ground texture is a landform property, not a component.
        self.assertIsNone(
            dialog.findChild(QtWidgets.QCheckBox, "component:landform:1:texture")
        )
        grass = dialog.findChild(QtWidgets.QCheckBox, "component:cover:1:0")
        self.assertIn("on flat_landform", grass.text())
        self.assertIsNotNone(dialog.findChild(QtWidgets.QCheckBox, "component:water"))
        # Rows still bind to the real nested path.
        grass.setChecked(True)
        self.application.processEvents()
        self.assertTrue(self.window.config.get(
            ("scene_description", "landforms", 1, "surface_objects", 0, "enabled")
        ))
        dialog.close()

    def test_scene_setup_keeps_exactly_one_terrain_heightfield_landform(self):
        dialog = SceneSetupDialog(self.window.config, self.window, launch=False)
        dip_rise = dialog.findChild(QtWidgets.QCheckBox, "component:landform:0")
        flat = dialog.findChild(QtWidgets.QCheckBox, "component:landform:1")
        vista = dialog.findChild(QtWidgets.QCheckBox, "component:landform:2")
        # The rule is stated on the dialog, not only enforced.
        notes = [label.text() for label in dialog.findChildren(QtWidgets.QLabel)]
        self.assertTrue(any(
            "Only one terrain-heightfield landform" in text
            and "right_dip_rise" in text and "flat_landform" in text
            for text in notes
        ))
        self.assertIn("heightfield", dip_rise.text())
        self.assertIn("heightfield", flat.text())
        self.assertNotIn("heightfield", vista.text())
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
        # Shaft compositing is deferred and not offered.
        self.assertIsNone(dialog.findChild(QtWidgets.QCheckBox, "setup_shaft_composite"))
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

    # -- entry form builder (Step A: undergrowth) --------------------------

    UNDERGROWTH = ("scene_description", "landforms", 1, "surface_objects", 4)

    def _field(self, page, *tail, cls=QtWidgets.QWidget):
        name = "field:" + ".".join(str(p) for p in self.UNDERGROWTH + tail)
        widget = page.findChild(cls, name)
        self.assertIsNotNone(widget, name)
        return widget

    def test_entry_page_shows_every_undergrowth_field_in_json_order(self):
        key = entry_page_key(self.UNDERGROWTH)
        self.assertIn(key, self.window.inspector.pages)
        page = self.window.inspector.pages[key]
        # Outline routes the undergrowth row to this page.
        pages = {c.key: c.page for c in scene_components(self.window.config)}
        self.assertEqual(pages["cover:1:4"], key)

        # Top-level fields, in the file's order.
        labels = [
            label.text()
            for label in page.findChildren(QtWidgets.QLabel)
            if label.text() in {"name", "enabled", "generator"}
        ]
        self.assertEqual(labels, ["name", "enabled", "generator"])
        self.assertEqual(self._field(page, "name", cls=QtWidgets.QLineEdit).text(), "undergrowth")
        self.assertFalse(self._field(page, "enabled", cls=QtWidgets.QCheckBox).isChecked())
        self.assertEqual(self._field(page, "generator", cls=QtWidgets.QLineEdit).text(), "undergrowth")

        # Brace-groups become titled sections, nested as the JSON nests them.
        sections = [g.title() for g in page.findChildren(QtWidgets.QGroupBox)]
        self.assertEqual(
            sections,
            ["CONSTRUCTION", "reflectance_variants", "POPULATION", "region",
             "exclusion", "patchiness"],
        )

        # construction
        self.assertEqual(self._field(page, "construction", "variants", cls=QtWidgets.QSpinBox).value(), 2)
        self.assertAlmostEqual(self._field(page, "construction", "scale", 0, cls=QtWidgets.QDoubleSpinBox).value(), 2.0)
        self.assertAlmostEqual(self._field(page, "construction", "scale", 1, cls=QtWidgets.QDoubleSpinBox).value(), 4.8)
        self.assertAlmostEqual(
            self._field(page, "construction", "reflectance_variants", 1, 1, cls=QtWidgets.QDoubleSpinBox).value(), 0.18
        )
        # population
        self.assertEqual(self._field(page, "population", "seed", cls=QtWidgets.QSpinBox).value(), 79)
        self.assertEqual(self._field(page, "population", "count", cls=QtWidgets.QSpinBox).value(), 140)
        self.assertAlmostEqual(self._field(page, "population", "region", "size", 1, cls=QtWidgets.QDoubleSpinBox).value(), 440.0)
        self.assertAlmostEqual(self._field(page, "population", "max_slope_degrees", cls=QtWidgets.QDoubleSpinBox).value(), 30.0)
        self.assertAlmostEqual(self._field(page, "population", "y_offset", cls=QtWidgets.QDoubleSpinBox).value(), 0.04)
        self.assertAlmostEqual(self._field(page, "population", "exclusion", "radius", cls=QtWidgets.QDoubleSpinBox).value(), 24.0)
        self.assertAlmostEqual(self._field(page, "population", "patchiness", "strength", cls=QtWidgets.QDoubleSpinBox).value(), 0.88)
        self.assertAlmostEqual(self._field(page, "population", "patchiness", "frequency", cls=QtWidgets.QDoubleSpinBox).value(), 0.020)

    def test_entry_page_controls_write_back_to_their_own_paths(self):
        page = self.window.inspector.pages[entry_page_key(self.UNDERGROWTH)]
        self._field(page, "population", "count", cls=QtWidgets.QSpinBox).setValue(150)
        self._field(page, "enabled", cls=QtWidgets.QCheckBox).setChecked(True)
        self._field(page, "construction", "scale", 1, cls=QtWidgets.QDoubleSpinBox).setValue(5.25)
        self._field(page, "population", "region", "center", 0, cls=QtWidgets.QDoubleSpinBox).setValue(12.0)
        self._field(page, "construction", "reflectance_variants", 0, 2, cls=QtWidgets.QDoubleSpinBox).setValue(0.05)
        self.application.processEvents()
        get = self.window.config.get
        self.assertEqual(get(self.UNDERGROWTH + ("population", "count")), 150)
        self.assertTrue(get(self.UNDERGROWTH + ("enabled",)))
        self.assertEqual(get(self.UNDERGROWTH + ("construction", "scale")), [2.0, 5.25])
        self.assertEqual(get(self.UNDERGROWTH + ("population", "region", "center")), [12.0, 0.0])
        self.assertEqual(get(self.UNDERGROWTH + ("construction", "reflectance_variants", 0)), [0.025, 0.13, 0.05])
        self.assertTrue(self.window.save_config())
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        undergrowth = data["scene_description"]["landforms"][1]["surface_objects"][4]
        self.assertEqual(undergrowth["population"]["count"], 150)
        self.assertEqual(undergrowth["construction"]["scale"], [2.0, 5.25])

    def test_value_controls_ignore_the_mouse_wheel(self):
        page = self.window.inspector.pages[entry_page_key(self.UNDERGROWTH)]
        count = self._field(page, "population", "count", cls=QtWidgets.QSpinBox)
        scale = self._field(page, "construction", "scale", 1, cls=QtWidgets.QDoubleSpinBox)
        before = (count.value(), scale.value())
        for widget in (count, scale):
            event = QtGui.QWheelEvent(
                QtCore.QPointF(5, 5), QtCore.QPointF(5, 5),
                QtCore.QPoint(0, 0), QtCore.QPoint(0, 120),
                QtCore.Qt.MouseButton.NoButton, QtCore.Qt.KeyboardModifier.NoModifier,
                QtCore.Qt.ScrollPhase.NoScrollPhase, False,
            )
            self.application.sendEvent(widget, event)
        self.application.processEvents()
        self.assertEqual((count.value(), scale.value()), before)
        # Same for every spin box and combo box in the window.
        for widget in self.window.findChildren(QtWidgets.QAbstractSpinBox):
            self.assertTrue(type(widget).__name__.startswith("NoWheel"), widget.objectName())
        for widget in self.window.findChildren(QtWidgets.QComboBox):
            self.assertTrue(type(widget).__name__.startswith("NoWheel"), widget.objectName())

    def test_scene_setup_toolbar_action_is_present(self):
        actions = {action.text() for action in self.window.findChildren(QtGui.QAction)}
        self.assertIn("Scene Setup…", actions)

    def test_file_names_and_paths_are_not_shown_in_the_gui(self):
        for name in ("pbrt_scene_filename", "remote_archive_path", "pbrt_executable_path"):
            self.assertIsNone(self.window.findChild(QtWidgets.QLineEdit, name), name)
        for widget in self.window.findChildren(QtWidgets.QWidget):
            self.assertFalse(widget.objectName().startswith("field:file_"), widget.objectName())

    def test_camera_page_shows_the_whole_camera_entry(self):
        page = self.window.inspector.pages[entry_page_key(("camera_settings",))]
        enabled = page.findChild(QtWidgets.QCheckBox, "field:camera_settings.enabled")
        camera_type = page.findChild(QtWidgets.QLineEdit, "field:camera_settings.type")
        eye_y = page.findChild(QtWidgets.QDoubleSpinBox, "field:camera_settings.look_at.eye.1")
        fov = page.findChild(QtWidgets.QDoubleSpinBox, "field:camera_settings.fov")
        self.assertTrue(enabled.isChecked())
        self.assertEqual(camera_type.text(), "perspective")
        self.assertAlmostEqual(eye_y.value(), 165.0)
        self.assertEqual([g.title() for g in page.findChildren(QtWidgets.QGroupBox)], ["LOOK_AT"])
        fov.setValue(47.5)
        self.application.processEvents()
        self.assertTrue(self.window.save_config())
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(data["camera_settings"]["fov"], 47.5)
        self.assertNotIn("scene", data)

    def test_render_page_is_grouped_as_the_json_minus_shaft(self):
        page = self.window.inspector.pages[entry_page_key(("render_settings",))]
        sections = [g.title() for g in page.findChildren(QtWidgets.QGroupBox)]
        self.assertEqual(sections, ["FILM", "SAMPLER", "INTEGRATOR", "BACKEND"])
        self.assertNotIn("SHAFT_COMPOSITE", sections)
        self.assertIsNone(page.findChild(QtWidgets.QWidget, "field:render_settings.shaft_composite.enabled"))
        sampler = page.findChild(QtWidgets.QLineEdit, "field:render_settings.sampler.type")
        integrator = page.findChild(QtWidgets.QLineEdit, "field:render_settings.integrator.type")
        backend = page.findChild(QtWidgets.QLineEdit, "field:render_settings.backend.type")
        statistics = page.findChild(QtWidgets.QCheckBox, "field:render_settings.backend.show_statistics")
        width = page.findChild(QtWidgets.QSpinBox, "field:render_settings.film.x_resolution")
        self.assertEqual(sampler.text(), "halton")
        self.assertEqual(integrator.text(), "volpath")
        self.assertEqual(backend.text(), "gpu")
        self.assertTrue(statistics.isChecked())
        self.assertEqual(width.value(), 2000)

        backend.setText("cpu")
        backend.editingFinished.emit()
        self.assertTrue(self.window.save_config())
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(data["render_settings"]["backend"]["type"], "cpu")
        self.assertNotIn("runtime", data)
        self.assertNotIn("pipeline", data)
        self.assertNotIn("scene", data)

    def test_sun_and_background_pages_show_their_entries_minus_shaft(self):
        sun = self.window.inspector.pages[entry_page_key(("scene_description", "sky", "sun"))]
        self.assertNotIn("LIGHT_SHAFTS", [g.title() for g in sun.findChildren(QtWidgets.QGroupBox)])
        temperature = sun.findChild(QtWidgets.QSpinBox, "field:scene_description.sky.sun.temperature")
        self.assertEqual(temperature.value(), 5700)
        astro = sun.findChild(QtWidgets.QCheckBox, "field:scene_description.sky.sun.use_astronomical_direction")
        self.assertFalse(astro.isChecked())
        background = self.window.inspector.pages[entry_page_key(("scene_description", "sky", "background"))]
        self.assertEqual([g.title() for g in background.findChildren(QtWidgets.QGroupBox)], ["ENVIRONMENT"])
        coverage = background.findChild(
            QtWidgets.QDoubleSpinBox, "field:scene_description.sky.background.environment.coverage"
        )
        self.assertIsNotNone(coverage)

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

    def test_paths_remain_editable_through_the_config_even_without_controls(self):
        self.window.inspector._set(
            ("file_paths", "remote_archive"), "gdrive:wipImages/pbrt-v4/path-control-test"
        )
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
