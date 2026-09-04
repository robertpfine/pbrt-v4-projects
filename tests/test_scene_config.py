import json
from pathlib import Path
import tempfile
import unittest

from scene_config import SceneConfig, SceneConfigConflictError, SceneConfigError
from generate import configured_space_colonization_trees


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
  "render_settings": {
    "film": { "x_resolution": 100, "y_resolution": 100 },
    "sampler": { "type": "halton", "pixel_samples": 4 },
    "integrator": { "type": "volpath", "max_depth": 8 },
    "backend": { "type": "cpu", "show_statistics": false },
    "shaft_composite": {
      "enabled": false,
      "shaft_light": "shaft_sun",
      "base_opacity": 1.0,
      "shaft_opacity": 0.4,
      "surface_reflectance_scale": 0.08,
      "terrain_reflectance_scale": 0.015,
      "blur_radius": 2.0
    }
  },
  "scene_description": {
    "mode": "new",
    "name": "Original Scene",
    "scene_context": {
      "date": "2026-06-21",
      "local_time": "08:00:00",
      "time_zone": "America/New_York",
      "latitude": 43.0,
      "longitude": -76.0,
      "world_north": [0.0, 0.0, 1.0]
    },
    "landforms": [
      {
        "name": "flat",
        "enabled": true,
        "placement": {
          "position": [0.0, 0.0, 0.0],
          "rotation_degrees": [0.0, 0.0, 0.0]
        },
        "geometry": {
          "patches": [{
            "name": "main_patch",
            "enabled": true,
            "generator": "plane",
            "dimensions": [10.0, 10.0],
            "subdivisions": [3, 3],
            "local_position": [0.0, 0.0, 0.0],
            "local_rotation_degrees": [0.0, 0.0, 0.0]
          }]
        },
        "topography": {
          "enabled": true,
          "generator": "terrain_heightfield",
          "parameters": {
            "slope": { "grade": 0.0 },
            "noise": { "amplitude": 0.0 }
          }
        },
        "surface": { "material": {}, "texture": {} },
        "surface_objects": [{
          "name": "grass",
          "enabled": true,
          "generator": "grass",
          "construction": {
            "surface": { "type": "diffuse" }
          },
          "population": {
            "layers": [{ "count": 10 }],
            "camera_frustum": { "enabled": false }
          }
        }, {
          "name": "poppies",
          "enabled": true,
          "generator": "poppy",
          "construction": {},
          "population": {
            "count": 20,
            "scale": [1.0, 2.0],
            "camera_frustum": {
              "enabled": true,
              "placement_reference": "flower"
            }
          }
        }]
      },
      {
        "name": "gully",
        "enabled": false,
        "placement": {
          "position": [0.0, 0.0, 0.0],
          "rotation_degrees": [0.0, 0.0, 0.0]
        },
        "geometry": {
          "patches": [{
            "name": "main_patch",
            "enabled": true,
            "generator": "plane",
            "dimensions": [10.0, 10.0],
            "subdivisions": [3, 3],
            "local_position": [0.0, 0.0, 0.0],
            "local_rotation_degrees": [0.0, 0.0, 0.0]
          }]
        },
        "topography": {
          "enabled": true,
          "generator": "terrain_heightfield",
          "parameters": {
            "slope": { "grade": 0.1 },
            "noise": { "amplitude": 1.0 }
          }
        },
        "surface": { "material": {}, "texture": {} },
        "surface_objects": []
      }
    ],
    "objects": [],
    "sky": {
      "background": { "enabled": true, "type": "infinite" },
      "sun": {
        "enabled": true,
        "type": "distant",
        "use_astronomical_direction": false,
        "from": [1, 1, 1],
        "to": [0, 0, 0],
        "light_shafts": {
          "light": { "enabled": false, "label": "shaft_sun" },
          "aperture": { "enabled": false, "light": "shaft_sun" }
        }
      },
      "cloud_grid_builder": {},
      "clouds": []
    },
    "atmosphere": {
      "fog": [{
        "name": "test_fog",
        "enabled": false,
        "boundary": {
          "active_shape": "sphere",
          "camera_inside": true,
          "sphere": { "center": [0.0, 0.0, 0.0], "radius": 10.0 },
          "box_alternative": { "enabled": false }
        },
        "density_field": { "enabled": false, "generator": "perlin" },
        "medium": {
          "name": "fog",
          "type": "uniformgrid",
          "absorption": 0.0,
          "scattering": 0.0,
          "anisotropy": 0.0
        }
      }],
      "haze": [],
      "mist": [],
      "rain": []
    }
  },
  "scene": {
    "landscape": {
      "water": { "enabled": false }
    },
    "geometry": []
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
            config.set(
                "scene_description.landforms.0.surface_objects.1.population.count",
                2600,
            )
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
            config.set(
                "scene_description.landforms.0.surface_objects.1.population.count",
                21,
            )
            path.write_text(path.read_text() + "\n", encoding="utf-8")
            with self.assertRaises(SceneConfigConflictError):
                config.save()

    def test_invalid_value_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path, source = self.make_config(directory)
            config = SceneConfig(path)
            config.set(
                "scene_description.landforms.0.surface_objects.1.population.scale",
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
                "scene_description.landforms.0.surface_objects.1.population."
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
                "scene_description.landforms.0.surface_objects.1.population."
                "camera_frustum",
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

    def test_invalid_render_settings_are_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path, source = self.make_config(directory)
            config = SceneConfig(path)
            config.set("render_settings.backend.type", "vulkan")
            config.set("render_settings.shaft_composite.blur_radius", -1.0)
            with self.assertRaises(SceneConfigError) as context:
                config.save()
            message = str(context.exception)
            self.assertIn("render_settings.backend.type must be cpu or gpu", message)
            self.assertIn(
                "render_settings.shaft_composite.blur_radius must be nonnegative",
                message,
            )
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_invalid_scene_description_and_context_are_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path, source = self.make_config(directory)
            config = SceneConfig(path)
            config.set("scene_description.mode", "legacy")
            config.set("scene_description.scene_context.date", "2026-02-30")
            config.set("scene_description.scene_context.local_time", "25:00:00")
            config.set(
                "scene_description.scene_context.time_zone", "Not/A_Time_Zone"
            )
            config.set("scene_description.scene_context.latitude", 91.0)
            config.set("scene_description.scene_context.longitude", -181.0)
            config.set(
                "scene_description.scene_context.world_north",
                [0.0, 1.0, 0.0],
            )
            with self.assertRaises(SceneConfigError) as context:
                config.save()
            message = str(context.exception)
            self.assertIn("scene_description.mode must be new", message)
            self.assertIn("scene_context.date must be a calendar date", message)
            self.assertIn("scene_context.local_time must be a valid time", message)
            self.assertIn(
                "scene_context.time_zone must be a valid IANA name", message
            )
            self.assertIn("scene_context.latitude must be between -90 and 90", message)
            self.assertIn(
                "scene_context.longitude must be between -180 and 180", message
            )
            self.assertIn(
                "scene_context.world_north must be a nonzero horizontal vector",
                message,
            )

    def test_unsupported_terrain_rotation_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path, source = self.make_config(directory)
            config = SceneConfig(path)
            config.set(
                "scene_description.landforms.0.placement.rotation_degrees",
                [0.0, 15.0, 0.0],
            )
            with self.assertRaisesRegex(
                SceneConfigError, "terrain_heightfield rotations must currently be zero"
            ):
                config.save()
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_current_scene_is_valid_and_describable(self):
        root = Path(__file__).resolve().parents[1]
        config = SceneConfig(root / "scene_workspace" / "config.json")
        self.assertEqual(config.validate(), [])
        description = config.describe()
        self.assertIn("Scene: Poppy Field Overcast 8AM Study (new)", description)
        self.assertIn("Context: 2026-06-21 08:00:00 America/New_York", description)
        self.assertIn("Landform: flat_landform", description)
        self.assertIn("Poppies:", description)
        self.assertIn("Water: disabled", description)
        self.assertIn("Distant hills: disabled, 0 layers", description)
        self.assertIn("Sky background: enabled", description)
        self.assertIn("Clouds: enabled", description)

    def test_grass_uses_unique_landform_surface_object_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            config = SceneConfig(path)
            self.assertEqual(
                config.surface_object_path("grass"),
                (
                    "scene_description",
                    "landforms",
                    0,
                    "surface_objects",
                    0,
                ),
            )
            self.assertEqual(
                config.surface_object_path("poppy"),
                (
                    "scene_description",
                    "landforms",
                    0,
                    "surface_objects",
                    1,
                ),
            )

    def test_obsolete_ground_grass_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scene"]["landscape"]["ground"] = {
                "details": {"grass": {"enabled": False}}
            }
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn(
                "obsolete scene.landscape.ground.details.grass must be "
                "removed after grass migration",
                SceneConfig(path).validate(),
            )

    def test_obsolete_ground_poppies_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scene"]["landscape"]["ground"] = {
                "details": {"poppies": {"enabled": False}}
            }
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn(
                "obsolete scene.landscape.ground.details.poppies must be "
                "removed after poppy migration",
                SceneConfig(path).validate(),
            )

    def test_obsolete_ground_litter_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scene"]["landscape"]["ground"] = {
                "details": {"litter": {"enabled": False}}
            }
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn(
                "obsolete scene.landscape.ground.details.litter must be "
                "removed after litter migration",
                SceneConfig(path).validate(),
            )

    def test_obsolete_ground_rocks_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scene"]["landscape"]["ground"] = {
                "details": {"rocks": {"enabled": False}}
            }
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertIn(
                "obsolete scene.landscape.ground.details.rocks must be "
                "removed after rock migration",
                SceneConfig(path).validate(),
            )

    def test_obsolete_ground_undergrowth_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scene"]["landscape"]["ground"] = {
                "details": {"undergrowth": {"enabled": False}}
            }
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = SceneConfig(path).validate()
            self.assertIn(
                "obsolete scene.landscape.ground must be removed after "
                "surface-object migration",
                errors,
            )
            self.assertIn(
                "obsolete scene.landscape.ground.details.undergrowth must be "
                "removed after undergrowth migration",
                errors,
            )

    def test_current_scene_uses_explicit_landscape_and_sky_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (root / "scene_workspace" / "config.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            list(config)[:5],
            [
                "file_names",
                "file_paths",
                "camera_settings",
                "render_settings",
                "scene_description",
            ],
        )
        self.assertNotIn("archive", config)
        self.assertNotIn("runtime", config)
        self.assertNotIn("pipeline", config)
        data = config["scene"]
        self.assertNotIn("name", data)
        self.assertNotIn("camera", data)
        for obsolete in ("film", "sampler", "integrator"):
            self.assertNotIn(obsolete, data)
        for obsolete in ("master_file", "output_filename", "generated_medium"):
            self.assertNotIn(obsolete, data)
        self.assertNotIn("terrain", data)
        self.assertNotIn("lsystem_trees", data)
        self.assertNotIn("trees", data)
        self.assertNotIn("grove", data)
        self.assertEqual(
            [
                landform["name"]
                for landform in config["scene_description"]["landforms"]
                if landform["enabled"]
            ],
            ["flat_landform", "vista_plane"],
        )
        vista = next(
            landform
            for landform in config["scene_description"]["landforms"]
            if landform["name"] == "vista_plane"
        )
        self.assertFalse(vista["topography"]["enabled"])
        self.assertEqual(
            vista["surface"]["texture"]["generator"],
            "vista_surface_mottle",
        )
        self.assertTrue(
            all(item.get("label") != "vista_plane" for item in data["geometry"])
        )
        self.assertNotIn("ground", data["landscape"])
        self.assertEqual(
            set(data["landscape"]),
            {"water"},
        )
        self.assertNotIn("sky", data)
        self.assertNotIn("lights", data)
        self.assertNotIn("fog", data)
        self.assertTrue(
            all(item.get("label") != "fog_volume" for item in data["geometry"])
        )
        sky = config["scene_description"]["sky"]
        self.assertEqual(
            set(sky), {"background", "sun", "cloud_grid_builder", "clouds"}
        )
        self.assertEqual(sky["background"]["type"], "infinite")
        self.assertFalse(sky["sun"]["use_astronomical_direction"])
        atmosphere = config["scene_description"]["atmosphere"]
        self.assertEqual(set(atmosphere), {"fog", "haze", "mist", "rain"})
        self.assertEqual([fog["name"] for fog in atmosphere["fog"]], ["ground_fog"])
        flat = next(
            landform
            for landform in config["scene_description"]["landforms"]
            if landform["name"] == "flat_landform"
        )
        self.assertEqual(
            [
                item["name"]
                for item in flat["surface_objects"]
                if item["generator"] == "lsystem_tree"
            ],
            ["live_oak", "fractal_tree"],
        )
        self.assertEqual(
            [
                item["name"]
                for item in flat["surface_objects"]
                if item["generator"] == "space_colonization_tree"
            ],
            ["space_colonization_tree_1", "space_colonization_tree_2"],
        )

    def test_space_colonization_generator_reads_landform_surface_objects(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (root / "scene_workspace" / "config.json").read_text(encoding="utf-8")
        )

        trees = configured_space_colonization_trees(config)

        self.assertEqual(len(trees), 2)
        self.assertEqual([tree["enabled"] for tree in trees], [False, False])
        self.assertEqual(
            [len(tree["instances"]["placements"]) for tree in trees],
            [7, 0],
        )

    def test_obsolete_lsystem_tree_array_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scene"]["lsystem_trees"] = []
            path.write_text(json.dumps(data), encoding="utf-8")

            self.assertIn(
                "obsolete scene.lsystem_trees must be removed after "
                "L-system tree migration",
                SceneConfig(path).validate(),
            )

    def test_obsolete_space_tree_and_grove_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scene"]["trees"] = []
            data["scene"]["grove"] = {"enabled": False}
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = SceneConfig(path).validate()

            self.assertIn(
                "obsolete scene.trees must be removed after "
                "space-colonization tree migration",
                errors,
            )
            self.assertIn(
                "obsolete scene.grove must be removed after "
                "space-colonization tree migration",
                errors,
            )

    def test_independent_object_schema_and_obsolete_phyllotaxis_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scene_description"]["objects"] = [{
                "name": "sunflower",
                "enabled": False,
                "placement": {
                    "position": [0.0, 0.0, 0.0],
                    "rotation_degrees": [0.0, 0.0, 0.0],
                },
                "geometry": {"generator": "planar_phyllotaxis"},
                "material": {},
                "construction": {
                    "count": 3,
                    "spacing": 1.0,
                    "center": [0.0, 0.0, 0.0],
                    "zones": [{"index_min": 0, "index_max": 2, "organ": {}}],
                },
            }]
            data["scene"]["planar_phyllotaxis"] = []
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = SceneConfig(path).validate()

            self.assertIn(
                "obsolete scene.planar_phyllotaxis must be removed after "
                "independent-object migration",
                errors,
            )
            self.assertEqual(
                [error for error in errors if "scene_description.objects" in error],
                [],
            )

    def test_obsolete_independent_volume_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scene"]["grid"] = {"enabled": False}
            data["scene"]["zones"] = []
            data["scene"]["geometry"] = [{"label": "volume_box"}]
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = SceneConfig(path).validate()

            self.assertIn(
                "obsolete scene.grid must be removed after "
                "independent-volume migration",
                errors,
            )
            self.assertIn(
                "obsolete scene.zones must be removed after "
                "independent-volume migration",
                errors,
            )
            self.assertIn(
                "obsolete scene.geometry independent volumes must be removed "
                "after independent-volume migration",
                errors,
            )

    def test_obsolete_fog_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scene"]["fog"] = {"enabled": False}
            data["scene"]["geometry"] = [{"label": "fog_volume"}]
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = SceneConfig(path).validate()

            self.assertIn(
                "obsolete scene.fog must be removed after atmosphere migration",
                errors,
            )
            self.assertIn(
                "obsolete scene.geometry fog_volume must be absorbed by fog",
                errors,
            )

    def test_obsolete_geometry_vista_plane_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scene"]["geometry"] = [{"label": "vista_plane"}]
            path.write_text(json.dumps(data), encoding="utf-8")

            self.assertIn(
                "obsolete scene.geometry vista_plane must be removed after "
                "vista landform migration",
                SceneConfig(path).validate(),
            )

    def test_obsolete_distant_hills_wrapper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.make_config(directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["scene"]["landscape"]["distant_hills"] = {
                "enabled": False,
                "layers": [],
            }
            path.write_text(json.dumps(data), encoding="utf-8")

            self.assertIn(
                "obsolete scene.landscape.distant_hills must be removed "
                "after distant-ridge migration",
                SceneConfig(path).validate(),
            )

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
            config.set("scene_description.landforms.0.enabled", False)
            config.set("scene_description.landforms.1.enabled", True)
            config.save()
            self.assertEqual(
                [
                    landform["name"]
                    for landform in json.loads(path.read_text())["scene_description"][
                        "landforms"
                    ]
                    if landform["enabled"]
                ],
                ["gully"],
            )


if __name__ == "__main__":
    unittest.main()
