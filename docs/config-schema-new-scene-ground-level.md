# Ground-Level Config Schema: Create a New Scene

Status: engineering draft derived from the approved architectural review
Scope: `scene_description.mode: "new"` and migration of the current live scene
Authority: `scene_workspace/config.json` remains the sole live configuration

## How this document is reviewed

This document translates the approved artistic architecture into exact field
ownership, validation rules, and current-to-proposed path mappings. It is not a
second runnable configuration. The artist is not expected to review every
generator leaf. Artist review is required only when a decision changes visible
terminology, the location of an artistic control, or the way a scene is built.

Implementation details and mechanical mappings are the engineering
responsibility of the application. Existing generator parameter blocks move
intact unless this document explicitly identifies a conversion.

## Non-negotiable invariants

- `scene_workspace/config.json` is the only authoritative scene JSON.
- Direct manual JSON editing remains supported.
- No artistic value is hidden behind a preset or invented schema label.
- A migration step moves a value; it never leaves competing live copies.
- A migrated scene preserves its existing values and rendered behavior.
- Blank-scene defaults never overwrite a migrated scene.
- The builder, validation, and Qt inspector change with each migrated section.
- Render inputs become immutable before the builder reads them.
- Render archives are local and on Google Drive. GitHub is separate.
- PNGs and generated PBRT files are not committed to GitHub.

## Notation and common types

Paths use `[]` for an array item and `<name>` for an artist-assigned descriptive
identifier.

| Type | Validation |
|---|---|
| `bool` | JSON `true` or `false` only |
| `number` | finite JSON number |
| `positive_number` | finite number greater than zero |
| `unit_number` | number from `0` through `1` |
| `integer` | JSON integer |
| `positive_integer` | integer greater than zero |
| `vec2` | array of exactly two finite numbers |
| `vec3` | array of exactly three finite numbers |
| `rgb` | `vec3`; components are nonnegative |
| `name` | nonempty descriptive string unique within its containing array |
| `path` | nonempty string; resolved according to the owning field |

Fields are required unless marked optional. An `enabled` value is always an
explicit boolean and never inferred from the presence of a block.

## Exact root order

```text
file_names
file_paths
camera_settings
render_settings
scene_description
```

No `runtime`, `pipeline`, or general `scene` wrapper remains after migration.

## 1. File names

```json
"file_names": {
  "pbrt_scene": "scene.pbrt",
  "working_image": "working_scene.png",
  "archive_image": "{scene_name}_{timestamp}.png"
}
```

| Field | Type | Rule |
|---|---|---|
| `pbrt_scene` | string | Working PBRT scene filename, not an archive path |
| `working_image` | string | PBRT film output filename during the run |
| `archive_image` | string | Must contain `{scene_name}` and `{timestamp}` |

Generated medium filenames are generator-owned artifacts and do not appear in
this artist-facing section.

### Current path mapping

| Current path | Proposed path |
|---|---|
| `scene.master_file` | `file_names.pbrt_scene` after separating its directory |
| `scene.output_filename` | `file_names.working_image` |
| derived archive filename | `file_names.archive_image` |
| `scene.generated_medium` | removed from artist-facing names; generator-managed |

## 2. File paths

```json
"file_paths": {
  "scene_files": "scene_workspace/scene_files",
  "local_archive": "Archive",
  "remote_archive": "gdrive:wipImages/pbrt-v4",
  "pbrt_executable": "/home/rpf4/pbrt-v4/build/pbrt"
}
```

| Field | Type | Rule |
|---|---|---|
| `scene_files` | path | Repository-relative working output directory |
| `local_archive` | path | Repository-relative or absolute local archive |
| `remote_archive` | path | Explicit rclone destination on Google Drive |
| `pbrt_executable` | path | Absolute PBRT-v4 executable path |

### Current path mapping

| Current path | Proposed path |
|---|---|
| directory portion of `scene.master_file` | `file_paths.scene_files` |
| `archive.remote_path` | `file_paths.remote_archive` |
| current repository `Archive/` convention | `file_paths.local_archive` |
| `runtime.pbrt_binary` | `file_paths.pbrt_executable` |

The current `pipeline.rclone_sync.enabled` switch is removed. A configured
`remote_archive` means the completed local bundle is also copied to Google
Drive. Remote failure must not invalidate or delete the completed local bundle.

## 3. Camera settings

```json
"camera_settings": {
  "enabled": true,
  "type": "perspective",
  "look_at": {
    "eye": [0.0, 2.0, 10.0],
    "look": [0.0, 0.0, 0.0],
    "up": [0.0, 1.0, 0.0]
  },
  "fov": 50.0
}
```

| Field | Type | Valid values |
|---|---|---|
| `enabled` | bool | `true` for a renderable new scene |
| `type` | string | first generation: `perspective` |
| `look_at.eye` | vec3 | eye point; must differ from `look` |
| `look_at.look` | vec3 | target point |
| `look_at.up` | vec3 | nonzero and not parallel to the viewing direction |
| `fov` | number | greater than `0` and less than `180` degrees |

`scene.camera.*` moves to `camera_settings.*` without numeric changes. The
values shown above are used only for a genuinely blank scene.

## 4. Render settings

```json
"render_settings": {
  "film": {
    "x_resolution": 2000,
    "y_resolution": 1450
  },
  "sampler": {
    "type": "halton",
    "pixel_samples": 512
  },
  "integrator": {
    "type": "volpath",
    "max_depth": 80
  },
  "backend": {
    "type": "gpu",
    "show_statistics": true
  },
  "shaft_composite": {
    "enabled": false,
    "shaft_light": "shaft_sun",
    "base_opacity": 1.0,
    "shaft_opacity": 0.40,
    "surface_reflectance_scale": 0.08,
    "terrain_reflectance_scale": 0.015,
    "blur_radius": 2.0
  }
}
```

| Field | Type | Validation |
|---|---|---|
| `film.x_resolution`, `film.y_resolution` | positive_integer | output pixels |
| `sampler.type` | string | first generation: `halton` |
| `sampler.pixel_samples` | positive_integer | PBRT samples per pixel |
| `integrator.type` | string | `volpath` for participating media |
| `integrator.max_depth` | positive_integer | PBRT path depth |
| `backend.type` | string | `cpu` or `gpu` |
| `backend.show_statistics` | bool | PBRT statistics display |
| `shaft_composite.enabled` | bool | selects ordinary or three-output workflow |
| `shaft_composite.shaft_light` | name | must resolve to the shaft light |
| opacity and reflectance scales | nonnegative number | no hidden normalization |
| `shaft_composite.blur_radius` | nonnegative number | pixels |

### Current path mapping

| Current path | Proposed path |
|---|---|
| `scene.film.*` | `render_settings.film.*` |
| `scene.sampler.*` | `render_settings.sampler.*` |
| `scene.integrator.*` | `render_settings.integrator.*` |
| `runtime.use_gpu` | `render_settings.backend.type` (`true` → `gpu`) |
| `runtime.show_stats` | `render_settings.backend.show_statistics` |
| `pipeline.shaft_composite.*` | `render_settings.shaft_composite.*` |
| `pipeline.build_scene.enabled` | removed; building is a required render phase |

The base pass, shaft pass, and composite are all retained whenever
`shaft_composite.enabled` is true.

## 5. Scene description shell

```json
"scene_description": {
  "mode": "new",
  "name": "Untitled Scene",
  "scene_context": {},
  "landforms": [],
  "water": {"enabled": false},
  "objects": [],
  "sky": {},
  "atmosphere": {}
}
```

| Field | Type | Rule |
|---|---|---|
| `mode` | string | this document defines only `new` |
| `name` | string | descriptive scene name, not a filename |

`scene.name` moves to `scene_description.name`. `mode` is added explicitly.

## 6. Scene context

```json
"scene_context": {
  "date": "2026-06-21",
  "local_time": "08:00:00",
  "time_zone": "America/New_York",
  "latitude": 43.0,
  "longitude": -76.0,
  "world_north": [0.0, 0.0, 1.0]
}
```

| Field | Type | Validation |
|---|---|---|
| `date` | string | ISO `YYYY-MM-DD` calendar date |
| `local_time` | string | 24-hour `HH:MM:SS` |
| `time_zone` | string | IANA time-zone name |
| `latitude` | number | `-90` through `90` degrees |
| `longitude` | number | `-180` through `180` degrees |
| `world_north` | vec3 | nonzero horizontal world-space direction |

These are new visible values. They affect sun direction only when the sun's
`use_astronomical_direction` is true.

## 7. Landforms

```json
{
  "name": "foreground_meadow",
  "enabled": true,
  "placement": {
    "position": [0.0, 0.0, 0.0],
    "rotation_degrees": [0.0, 0.0, 0.0]
  },
  "geometry": {
    "patches": []
  },
  "topography": {
    "enabled": false,
    "generator": "terrain_heightfield",
    "parameters": {}
  },
  "surface": {
    "material": {},
    "texture": {}
  },
  "surface_objects": []
}
```

### Landform fields

| Field | Type | Rule |
|---|---|---|
| `name` | name | descriptive identifier only |
| `enabled` | bool | independent per landform |
| `placement.position` | vec3 | world-space translation |
| `placement.rotation_degrees` | vec3 | X, Y, Z rotations |
| `geometry.patches` | array | one or more constituent surfaces |
| `topography.enabled` | bool | whether the shared elevation generator acts |
| `topography.generator` | string | registered Art Studio algorithm |
| `topography.parameters` | object | visible inputs owned by that algorithm |
| `surface.material` | object | one material for the landform |
| `surface.texture` | object | one composable texture system |
| `surface_objects` | array | things placed on or growing from the surface |

### Plane patch contract

```json
{
  "name": "main_patch",
  "enabled": true,
  "generator": "plane",
  "dimensions": [3000.0, 2800.0],
  "subdivisions": [401, 373],
  "local_position": [0.0, 0.0, 0.0],
  "local_rotation_degrees": [0.0, 0.0, 0.0]
}
```

`dimensions` is a positive `vec2`; `subdivisions` contains two integers of at
least `2`. First-generation `plane` produces a rectangular mesh. Additional
footprints are later generator extensions, not a general boundary block.

### Current ground mapping

Each entry at `scene.landscape.ground.landforms.<name>` becomes one item in
`scene_description.landforms[]`:

| Current path | Proposed ownership |
|---|---|
| `<landform>.center` and `<landform>.base_height` | `placement.position` |
| `<landform>.size` | `geometry.patches[main_patch].dimensions` |
| `<landform>.resolution` | `geometry.patches[main_patch].subdivisions` |
| `<landform>.slope` | `topography.parameters.slope` |
| `<landform>.noise` | `topography.parameters.noise` |
| `<landform>.right_profile` | `topography.parameters.right_profile` |
| `ground.material` | `surface.material` of the migrated ground landform |
| `ground.details.surface` | that landform's `surface.texture` |

`ground.active_landform` disappears. The selected entry becomes enabled when
the ground module is enabled; other retained alternatives become independently
disabled landforms.

The existing `vista_plane` geometry becomes its own `vista_plane` landform.
Its transformed rectangle becomes a `plane` patch, its diffuse material becomes
`surface.material`, and `surface_mottle` becomes `surface.texture`. The current
world-space placement and appearance values are preserved numerically.

Every enabled distant-hill layer becomes a separate landform using the
registered `distant_ridge` topography generator. Its current `center`, `size`,
`rotation_degrees`, `resolution`, `base_elevation`, `ridge_base_height`,
`cross_section`, `peaks`, `noise`, and `material` values remain visible and
owned by that landform.

## 8. Landform surface objects

```json
{
  "name": "poppy_field",
  "enabled": true,
  "generator": "poppy",
  "construction": {},
  "population": {}
}
```

`generator` selects registered code and supplies no hidden artistic values.
`construction` describes one generated form. `population` describes placement
of copies on the owning landform.

### Existing ground-detail mapping

The following blocks move under the active ground landform's
`surface_objects[]`:

| Current block | Generator | Construction owns | Population owns |
|---|---|---|---|
| `details.grass` | `grass` | `blade`, `tuft`, `surface`, `reflectance_variants` | `seed`, `variants`, `layers`, `region`, `max_slope_degrees`, `y_offset`, `exclusion`, `patchiness`, `camera_frustum`, `extension` |
| `details.poppies` | `poppy` | all flower color/material fields and `tropism` | `seed`, `count`, `variants`, `scale`, `region`, `max_slope_degrees`, `y_offset`, `exclusion`, `patchiness`, `camera_frustum`, `extension` |
| `details.litter` | `litter` | `variants`, `scale`, `reflectance_variants` | `seed`, `count`, `region`, `max_slope_degrees`, `y_offset`, `exclusion`, `patchiness`, `attraction` |
| `details.rocks` | `rock_scatter` | `variants`, `scale`, `reflectance_variants` | `seed`, `count`, `region`, `max_slope_degrees`, `y_offset`, `exclusion`, `patchiness` |
| `details.undergrowth` | `undergrowth` | `variants`, `scale`, `reflectance_variants` | `seed`, `count`, `region`, `max_slope_degrees`, `y_offset`, `exclusion`, `patchiness` |

All descendants listed in those blocks retain their current names and numeric
values during prototype migration. In particular, grass blade bend, lean,
tropism, tip droop, segment count, and depth-fade controls remain exposed.

### Tree mapping

- Each `scene.trees[]` entry becomes a `space_colonization_tree` surface object.
- Each `scene.lsystem_trees[]` entry becomes an `lsystem_tree` surface object.
- All current construction fields—including recursion, branching, bend,
  tropism, foliage, thickening, and material controls—move intact beneath
  `construction`.
- Root or origin placement and existing instance arrays move beneath
  `population`.
- The current `scene.grove` instance list is folded into the selected tree's
  `population`; the separate global grove block disappears.

Reusable source-object libraries remain a second-generation concern. This
first migration preserves the existing rendered instances without introducing
a new shared-object system.

## 9. Independent objects

Every item has a descriptive `name`, explicit `enabled`, `placement`, material,
and exactly one geometry source:

```json
{
  "name": "surreal_sphere",
  "enabled": false,
  "placement": {
    "position": [0.0, 100.0, -500.0],
    "rotation_degrees": [0.0, 0.0, 0.0]
  },
  "geometry": {
    "pbrt_shape": "sphere",
    "parameters": {"radius": 100.0}
  },
  "material": {
    "type": "diffuse",
    "reflectance": [0.8, 0.1, 0.2],
    "reflectance_scale": 1.0
  }
}
```

`pbrt_shape` identifies direct PBRT shape functionality. `generator` identifies
an Art Studio construction algorithm. They are never aliases.

The current `scene.planar_phyllotaxis[]` sunflower-head definitions migrate as
independent generated objects with generator `planar_phyllotaxis`; all existing
surface, zones, organ, support, stem, leaf, bract, and material controls remain
intact beneath `construction`.

Disabled legacy `volume_sphere` and `volume_box` geometry can be retained as
self-contained disabled objects with their medium definitions. They must not be
renamed as atmosphere. The explicit `fog_volume` boundary is absorbed by the
fog object that owns it.

## 10. Sky

### Infinite background

```json
"background": {
  "enabled": true,
  "type": "infinite",
  "color_mode": "rgb",
  "color": [1.0, 1.0, 1.0],
  "scale": 1.0
}
```

`type` is the PBRT-v4 light type and must be `infinite` in the first generation.
`color_mode` is `rgb`; `color` is nonnegative RGB; `scale` is nonnegative. The
shown values are blank-scene defaults only. `scene.sky.background.*` moves
without value changes for migrated scenes.

### Sun

```json
"sun": {
  "enabled": false,
  "type": "distant",
  "use_astronomical_direction": true,
  "from": [0.0, 1.0, 0.0],
  "to": [0.0, 0.0, 0.0],
  "color_mode": "blackbody",
  "temperature": 5700,
  "scale": 1.0
}
```

| Field | Validation |
|---|---|
| `type` | first generation: PBRT `distant` |
| `use_astronomical_direction` | bool; sole direction-mode selector |
| `from`, `to` | vec3; used only when the boolean is false |
| `color_mode` | `blackbody` or `rgb` |
| `temperature` | positive number when blackbody mode is active |
| `color` | nonnegative RGB when RGB mode is active |
| `scale` | nonnegative number |

The active current `morning_sun` maps here with
`use_astronomical_direction: false`, preserving its PBRT `from` and `to` values.
The current `shaft_sun` and `sun_aperture` remain a self-contained light-shaft
subsystem owned by the sun; all their implemented fields move intact. Rejected,
disabled point- and spotlight experiments remain preserved in checkpoint
history and are not silently reclassified as sky.

## 11. Clouds

Each cloud is self-contained:

```json
{
  "name": "overcast_cloud_deck",
  "enabled": true,
  "placement": {
    "position": [-15000.0, 850.0, -10000.0]
  },
  "dimensions": [50000.0, 800.0, 26000.0],
  "boundary": {
    "mode": "axis_aligned"
  },
  "density_field": {
    "generator": "mottled_veil",
    "resolution": [160, 40, 120],
    "shape": {},
    "noise": {},
    "depth_slope": {},
    "depth_profile": {}
  },
  "medium": {
    "type": "rgbgrid",
    "density_scale": 0.90,
    "scattering": [0.0028, 0.0030, 0.0032],
    "absorption": [0.00045, 0.00050, 0.00055],
    "anisotropy": 0.25,
    "underside": {}
  }
}
```

| Field | Validation |
|---|---|
| `placement.position` | vec3 cloud center |
| `dimensions` | positive vec3 |
| `boundary.mode` | `axis_aligned` (legacy default) or `corner_prism` |
| `boundary.bottom_corners` | four named world-space vec3 values for `corner_prism` |
| `boundary.thickness` | positive vertical extrusion for `corner_prism` |
| `density_field.generator` | `lobed` or `mottled_veil` initially |
| `density_field.resolution` | three integers, each at least `2` |
| `density_field.shape` | current fades/profile fields moved intact |
| `density_field.noise` | current fractal-noise fields moved intact |
| `density_field.depth_slope` | current `enabled` and `far_y_offset` |
| `density_field.depth_profile` | optional explicit far-depth density falloff |
| `density_field.lobes` | required nonempty array for `lobed` |
| `medium.type` | emitted PBRT type: `uniformgrid` or `rgbgrid` |
| `medium.density_scale` | nonnegative number |
| `medium.scattering`, `medium.absorption` | nonnegative RGB |
| `medium.anisotropy` | greater than `-1` and less than `1` |
| `medium.underside` | current underside controls moved intact |

`corner_prism` makes the four bottom vertices authoritative for the medium
boundary. The required order is `near_left`, `near_right`, `far_right`, then
`far_left`; the names must trace a non-crossing convex footprint in the XZ
plane. The four points must be coplanar. `thickness` derives the top vertices
by adding `[0, thickness, 0]`, so the result is a closed vertical extrusion.
`density_field.depth_slope.enabled` must be false in this mode.

For a mottled veil, `noise.edge_fade_fraction` may remain the legacy
`[x, y, z]` triple, which applies symmetric fades to opposite faces, or become
an explicit face object:

```json
"edge_fade_fraction": {
  "left": 0.08,
  "right": 0.08,
  "bottom": 0.15,
  "top": 0.15,
  "near": 0.10,
  "far": 0.0
}
```

Each value is a fraction from `0` through `1`. In explicit face form, zero
means no density fade at that face. The camera eye is rejected if it lies
inside any enabled cloud boundary.

For every current `scene.sky.clouds.formations[]` item, `center`, `size`,
`resolution`, `form`, `lobes`, and local overrides move to the corresponding
self-contained cloud. The current shared `shape`, `fractal_noise`, and
`appearance` values are copied into each cloud that actually used them, then
the shared source blocks are removed. No hidden shared cloud defaults remain.

## 12. Normalized C++ cloud-grid contract

The C++ helper does not read `config.json`. Python resolves one self-contained
cloud into this versioned job:

```json
{
  "contract_version": 1,
  "name": "overcast_cloud_deck",
  "medium_name": "cloud_0_overcast_cloud_deck",
  "generator": "mottled_veil",
  "center": [-15000.0, 850.0, -10000.0],
  "dimensions": [50000.0, 800.0, 26000.0],
  "boundary": {
    "mode": "axis_aligned"
  },
  "resolution": [160, 40, 120],
  "density_field": {
    "shape": {},
    "noise": {},
    "depth_slope": {},
    "depth_profile": {},
    "lobes": []
  },
  "medium": {
    "type": "rgbgrid",
    "density_scale": 0.90,
    "scattering": [0.0028, 0.0030, 0.0032],
    "absorption": [0.00045, 0.00050, 0.00055],
    "anisotropy": 0.25,
    "underside": {}
  }
}
```

The contract contains resolved values only: no inheritance, live-config paths,
archive paths, camera values, or renderer settings. The snapshot bundle retains
this exact job specification.

The initial command interface is:

```text
cloud_grid_builder --spec <job.json> --output <medium.pbrt> --threads <count>
```

The output is a PBRT medium declaration compatible with the current builder's
`uniformgrid` or `rgbgrid` output. The implemented CPU version is deterministic
for identical inputs across single- and multi-thread operation. Its automated
small-grid tests compare both cloud forms and the density and optical grids
against the Python reference with an absolute tolerance of `1.1e-5` (the PBRT
arrays are intentionally serialized to five decimal places). Python remains an
explicit fallback.

Grid-build timing ends when the medium file is complete. PBRT render timing
starts separately. This prevents a faster generator from concealing an
intrinsically expensive volumetric render.

In the legacy live configuration, the temporary pre-migration technical switch
is kept adjacent to the cloud module at `scene.sky.clouds.grid_builder`. It owns
only `backend`, `executable`, `threads`, and `fallback_to_python`; it does not
hide or relocate any artistic cloud value. The current 160×40×120 overcast job
builds 768,000 voxels in about 0.55 seconds with automatic CPU threading on the
development machine, compared with about 5.77 seconds for the Python reference
before PBRT text formatting. A complete frozen scene build still takes roughly
209 seconds and produces a roughly 1.04 GB PBRT file because of the rest of the
current scene expansion; that cost is distinct from cloud-grid construction.

## 13. Atmosphere

```json
"atmosphere": {
  "fog": [],
  "haze": [],
  "mist": [],
  "rain": []
}
```

### Fog

The current `scene.fog` becomes one named fog object. It owns:

- placement/boundary: `boundary_center`, `boundary_radius`, `camera_inside`;
- density construction: the complete current `noise` block; and
- medium optics: `sigma_a`, `sigma_s`, and `g`.

The current noise type, resolution, bounds, seed, frequency, octaves,
persistence, lacunarity, base density, contrast, and height-falloff fields all
remain visible. Haze and mist remain empty placeholders with no generator or
hidden defaults.

### Rain

Every current `scene.rain.curtains[]` item becomes one independently enabled
rain object. Its `center`, `size`, and `resolution` remain object-local. The
current shared `pattern` and `appearance` fields are copied into each curtain
that used them, then the shared blocks are removed. Scattering, absorption,
anisotropy, fractal frequencies, coverage, softness, contrast, edge fades,
wind direction, and wind tilt remain explicit.

Clouds never appear under atmosphere.

## 14. Water placeholder

```json
"water": {
  "enabled": false
}
```

This is a visible `Yes_PH` placeholder only. It has no generator, implied
geometry, default material, or rendering behavior in this generation.

## 15. Legacy direct-volume experiment

The disabled `scene.grid`, `scene.zones`, `volume_sphere`, and `volume_box`
belong to an older direct `rgbgrid` experiment. They are not atmosphere names.
If retained in the new schema, each boundary becomes a disabled independent
object that owns a copy of the medium construction it references. Their current
grid dimensions, axis, bounds, absorption, emission, noise, and spectral-zone
values remain intact. This migration is preservation work, not a model for the
cloud or atmosphere hierarchy.

## 16. Mandatory render snapshot and archive transaction

One render request performs this ordered transaction:

1. Validate the authoritative live JSON.
2. Allocate one collision-safe render identifier and timestamp.
3. Create a private run workspace.
4. Freeze the JSON, builder, imported generators, render scripts, and normalized
   C++ grid jobs before any builder consumes them.
5. Build only from the frozen inputs.
6. Render only the frozen PBRT scene and medium files.
7. Write a manifest containing hashes, commands, versions, timings, and status.
8. Finalize the complete bundle into `file_paths.local_archive` without
   overwriting an existing bundle.
9. Copy that same completed bundle to `file_paths.remote_archive` on Google
   Drive without deleting or overwriting unrelated files.

Snapshotting is mandatory and has no JSON switch. A Google Drive failure is
reported clearly and remains retryable from the completed local archive.

## 17. Mechanical current-to-proposed family map

| Current family | Proposed family |
|---|---|
| `archive.*` | `file_paths.*` plus mandatory archive behavior |
| `runtime.*` | `file_paths.pbrt_executable` and `render_settings.backend.*` |
| `pipeline.shaft_composite.*` | `render_settings.shaft_composite.*` |
| `pipeline.build_scene.*` | mandatory render phase; no artist switch |
| `pipeline.rclone_sync.*` | implied by configured Google Drive destination |
| `scene.name` | `scene_description.name` |
| `scene.master_file` | `file_paths.scene_files` + `file_names.pbrt_scene` |
| `scene.output_filename` | `file_names.working_image` |
| `scene.camera.*` | `camera_settings.*` |
| `scene.film.*` | `render_settings.film.*` |
| `scene.sampler.*` | `render_settings.sampler.*` |
| `scene.integrator.*` | `render_settings.integrator.*` |
| `scene.landscape.ground.landforms.*` | `scene_description.landforms[]` |
| `scene.landscape.ground.details.surface.*` | owning landform `surface.texture.*` |
| `scene.landscape.ground.details.<object>.*` | owning landform `surface_objects[]` |
| `scene.landscape.distant_hills.layers[]` | separate `landforms[]` entries |
| `scene.geometry[vista_plane]` | `landforms[vista_plane]` |
| `scene.geometry[fog_volume]` | owned by `atmosphere.fog[]` |
| `scene.geometry[volume_sphere/box]` | disabled independent volume objects |
| `scene.planar_phyllotaxis[]` | independent generated `objects[]` |
| `scene.trees[]` | owning landform `surface_objects[]` |
| `scene.lsystem_trees[]` | owning landform `surface_objects[]` |
| `scene.grove.*` | selected tree `population.*` |
| `scene.sky.background.*` | `scene_description.sky.background.*` |
| active distant sun in `scene.lights[]` | `scene_description.sky.sun.*` |
| `scene.sun_aperture.*` and shaft sun | `scene_description.sky.sun.light_shafts.*` |
| `scene.sky.clouds.*` | self-contained `scene_description.sky.clouds[]` |
| `scene.fog.*` | self-contained `scene_description.atmosphere.fog[]` |
| `scene.rain.*` | self-contained `scene_description.atmosphere.rain[]` |
| `scene.landscape.water.*` | `scene_description.water.*` placeholder |
| `scene.grid.*`, `scene.zones.*` | disabled independent legacy volume objects |

## 18. Migration acceptance gate for every stage

A stage is complete only when:

- the old live path is absent;
- the new live path contains the preserved value;
- no compatibility default silently changes an artistic value;
- every artistically meaningful fallback currently supplied by source code has
  been materialized as an explicit configuration value or formally classified
  as a non-artistic implementation constant;
- the builder reads the new path;
- the validator reports the new path in useful language;
- the Qt inspector exposes the new path without reformatting unrelated JSON;
- unit and integration tests pass;
- generated PBRT structure is equivalent apart from expected comments or
  ordering that cannot affect rendering;
- any required bounded visual comparison is accepted; and
- the stable source/configuration/documentation state is committed and pushed.

The live migration does not begin until this draft, mandatory snapshotting, and
the CPU C++ cloud-grid generator have reached their approved prerequisite
states.

## 19. Current code-consumer map

This table establishes which implementation must change when a configuration
family moves. Line numbers are intentionally omitted because they will shift
during migration.

| Configuration responsibility | Current consumer or producer |
|---|---|
| paths, PBRT invocation, ordinary archive | `render_pipeline.sh` |
| shaft passes and composite archive | `render_shaft_composite.py` |
| formatting-preserving edits and validation | `scene_config.py` |
| Qt inspection and artist controls | `pbrt_v4_art_studio.py` |
| camera, film, sampler, integrator, lights, direct geometry | `scene_workspace/build_scene.py` |
| terrain elevation and placement | `terrain.py`, called by `build_scene.py` |
| grass, poppies, rocks, litter, undergrowth | `terrain_details.py`, called by `build_scene.py` |
| ground surface maps | `terrain_surface_texture.py`, called by `build_scene.py` |
| vista surface mottling | `vista_surface_texture.py`, called by `build_scene.py` |
| distant ridge landforms | `distant_hills.py`, called by `build_scene.py` |
| cloud density and optics | `clouds.py`, called by `build_scene.py` |
| rain-curtain density and optics | `rain.py`, called by `build_scene.py` |
| L-system/fractal trees | `fractal_tree.py` and `lsystem.py`, called by `build_scene.py` |
| space-colonization trees and foliage | `generate.py`, `space_col.py`, and `foliage.py` |
| planar phyllotaxis | `phyllotaxis.py`, called by `build_scene.py` |
| regression coverage | the corresponding files under `tests/` |

Each migration stage updates every applicable consumer in this table before
the old path is removed.
