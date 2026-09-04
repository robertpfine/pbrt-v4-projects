# Live Configuration Migration Progress — 2026-09-04

Status: Stage 1 implementation and validation complete

## Authority and starting point

- `scene_workspace/config.json` remains the sole authoritative live scene
  configuration. No second runnable configuration will be created.
- Active branch: `pbrt-v4-art-studio`.
- Migration starts from pushed checkpoint `1346745`, after the C++ cloud-grid
  implementation passed complete Python-versus-C++ render validation.
- The approved architectural basis is the fourteen resolved decisions in
  `docs/config-schema-new-scene.md` and their engineering translation in
  `docs/config-schema-new-scene-ground-level.md`.
- Each stage moves values rather than duplicating them. The builder, immutable
  snapshot transaction, pipeline, validator, Qt inspector, composite workflow,
  generators, and tests must agree before a stage is checkpointed.

## Approved migration order

1. File names and file paths.
2. Camera settings.
3. Render settings.
4. `scene_description` shell and context.
5. Landforms and their surface objects, one generator at a time.
6. Independent objects.
7. Sky background, sun, and individual clouds.
8. Atmosphere components.
9. Disabled water placeholder.
10. Removal of obsolete temporary compatibility code.

## Stage 1 — file names and file paths

### Exact target

The first five root sections become ordered as follows while later legacy
sections remain temporarily in place for their own stages:

```text
file_names
file_paths
runtime
pipeline
scene
```

The new values are:

```json
"file_names": {
  "pbrt_scene": "scene.pbrt",
  "working_image": "working_scene.png",
  "archive_image": "{scene_name}_{timestamp}.png"
},
"file_paths": {
  "scene_files": "scene_workspace/scene_files",
  "local_archive": "Archive",
  "remote_archive": "gdrive:wipImages/pbrt-v4",
  "pbrt_executable": "/home/rpf4/pbrt-v4/build/pbrt"
}
```

Moved or removed legacy values:

| Legacy path | Stage 1 result |
|---|---|
| `scene.master_file` | split into `file_paths.scene_files` and `file_names.pbrt_scene` |
| `scene.output_filename` | moved to `file_names.working_image` |
| derived archive naming | made explicit at `file_names.archive_image` |
| `archive.remote_path` | moved to `file_paths.remote_archive`; old `archive` root removed |
| repository `Archive/` convention | made explicit at `file_paths.local_archive` |
| `runtime.pbrt_binary` | moved to `file_paths.pbrt_executable` |
| `scene.generated_medium` | removed; direct-volume medium name becomes generator-owned |

`pipeline.rclone_sync` is removed because a configured
`file_paths.remote_archive` now means that synchronization is always attempted
after successful local archival. Remote failure remains non-destructive.
`runtime.use_gpu`, `runtime.show_stats`, the remaining `pipeline.*` controls,
and the remaining `scene.*` values do not move during this stage.

### Consumer inventory completed

- `render_pipeline.sh`: snapshot paths, PBRT executable, working PBRT scene,
  archive filename/directory, and remote destination.
- `render_snapshot.py`: field validation, collision detection, frozen
  scene-files copying, normalized cloud-job archival, and returned paths.
- `scene_workspace/build_scene.py`: complete PBRT output, film working image,
  generator-owned direct medium, cloud jobs, terrain/vista textures, and tree
  include paths.
- `render_shaft_composite.py`: base/shaft PBRT names, PBRT executable, archive
  directory and pattern, remote destination, and archived PBRT locations.
- `generate.py`, `space_col.py`, and `foliage.py`: generated tree and foliage
  files beneath the configured scene-files directory.
- `scene_config.py`: exact Stage 1 validation and useful new-path errors.
- `pbrt_v4_art_studio.py`: exact-value inspection/editing and latest-render
  discovery from the configured local archive.
- `tests/test_render_snapshot.py`, `tests/test_scene_config.py`, and GUI tests:
  migration regression coverage and explicit absence of the old paths.
- Focused documentation that names active legacy paths will be updated with the
  completed stage.

### Acceptance requirements

- All seven old live values/paths listed above are absent.
- The live values are numerically and textually preserved at their new homes.
- No compatibility reader accepts both old and new paths.
- Direct builder use and both render workflows resolve the same configured
  directories safely.
- Manual JSON editing and formatting-preserving GUI saves continue to work.
- Tests cover invalid filenames, unsafe scene-file paths, archive templating,
  frozen input behavior, ordinary rendering, composite rendering, and Qt
  discovery of the local archive.
- Full test suites and shell syntax checks pass.
- A non-rendering structural scene comparison confirms unchanged PBRT output
  for the same artistic configuration.

### Progress record

- Completed the initial repository-wide consumer search.
- Confirmed that hard-coded scene-file assumptions also existed in the tree and
  foliage generators and must be migrated in this stage; changing only the
  shell pipeline would leave `file_paths.scene_files` non-authoritative.
- Confirmed that no production render is required for this structural stage.
- Moved all seven live values into `file_names` and `file_paths`; removed the
  complete old `archive` root, `runtime.pbrt_binary`, `scene.master_file`,
  `scene.output_filename`, and `scene.generated_medium` without compatibility
  copies.
- Removed `pipeline.rclone_sync`; both ordinary and composite workflows now
  attempt the configured remote copy after the complete local archive exists,
  and preserve the local bundle if the remote operation fails.
- Updated ordinary and shaft-composite pipelines, immutable snapshot creation
  and finalization, direct scene building, cloud/texture/direct-volume output,
  tree and foliage generation, Qt latest-image discovery, and configuration
  validation to consume the new paths.
- The legacy `runtime` root now contains only the GPU/statistics controls that
  intentionally remain until the render-settings stage.
- Added exact-value Qt fields for all three configured filenames and all four
  configured paths. Formatting-preserving saves use the same authoritative
  JSON.
- Added tests for archive-pattern resolution, custom archive directories,
  unsafe PBRT filenames, escaping scene-file directories, composite pass
  filenames, absence of old live fields, new-path validation errors, configured
  builder output, and Qt field exposure.
- First focused regression pass found one Qt refresh defect: the common blocked
  widget helper assumed every non-checkbox/non-combobox had `setValue`.
  `QLineEdit` now refreshes through `setText`; the rerun passed.
- Hardened every render entry path against unsafe values. The snapshot and
  direct builder reject filename directory components, `.`/`..`, absolute or
  escaping generated-output directories, unsupported archive placeholders,
  and obsolete Stage 1 keys. The archive image suffix is deliberately the
  exact lowercase `.png` expected by the shell finalization logic.
- Corrected snapshot-source exclusion to follow
  `file_paths.scene_files`. A regression pipeline using
  `generated/scenes` proves generated PBRT output is excluded from the source
  tarball even when the directory has no legacy `scene_files` component.
- The complete `.venv` suite ran 86 tests: 79 passed and seven were skipped
  only where that environment intentionally lacks NumPy/Pillow-backed
  subsystems. The system-Python non-GUI suite passed all 75 tests, including
  the NumPy/Pillow composite and atmospheric coverage. System Python does not
  contain PySide6, so GUI tests are intentionally run in `.venv`.
- The live configuration validates with zero errors. Python byte-compilation
  and shell syntax checks for all active entry points pass.

### Exact migration audit

A mechanical comparison starts from checkpoint `1346745`, performs only the
approved Stage 1 transformations, and compares the result to the live JSON.
It reports `stage_one_only True`; the live root order begins exactly
`file_names`, `file_paths`, `runtime`, `pipeline`, `scene`.

The first formulation of this audit incorrectly compared old
scene-workspace-relative `scene_files` to the new repository-relative path and
therefore reported false. Adding the required `scene_workspace/` coordinate
conversion made the audit exact. No live JSON was changed in response to that
test-script error.

### Structural PBRT comparison

The archived `020525` diagnostic render settings were temporarily applied to
the sole live JSON, the migrated builder was run without launching PBRT, and
the diagnostic fields were restored to the current live values. The resulting
scene is byte-for-byte identical to the pre-migration builder output:

```text
size:    117,462,947 bytes
SHA-256: c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
```

The generated, gitignored `scene_workspace/scene_files/scene.pbrt` intentionally
remains this bounded diagnostic artifact while the authoritative JSON is back
at the current full overcast/vegetation values. This is safe because
`pipeline.build_scene.enabled` is true and every normal render rebuilds from
its frozen authoritative configuration. Rebuilding the full 1.044 GB scene
again would add cost without strengthening the already exact comparison.

### Stage result

All acceptance requirements for Stage 1 are satisfied. No production render
was needed or launched. After the GitHub and continuity-archive checkpoint, the
next migration stage is the exact move of `scene.camera` to root
`camera_settings`, with builder, placement consumers, validator, Qt inspector,
and tests changing together.

## Stage 2 — camera settings

Status: implementation and validation complete from pushed Stage 1 checkpoint
`0e77a3e`

### Exact target

The camera block moves once from `scene.camera` to the root, immediately after
`file_paths`:

```json
"camera_settings": {
  "enabled": true,
  "type": "perspective",
  "look_at": {
    "eye":  [290.0, 165.0, 365.0],
    "look": [5.0, 155.0, -5.0],
    "up":   [0, 1, 0]
  },
  "fov": 50.0
}
```

All existing artistic and numeric values are preserved. `type: "perspective"`
makes the builder's existing hardcoded PBRT camera type explicit, as required
by the approved schema; it does not change rendered behavior. `scene.camera`
is removed rather than retained as a compatibility copy.

### Consumer inventory

- `scene_workspace/build_scene.py` emits the PBRT `LookAt` and `Camera`
  directives and passes the same camera to terrain-detail placement.
- `terrain_details.py` consumes the camera object passed by the builder for
  visible-frustum placement and depth fade. It contains no JSON ownership path
  and therefore needs no schema-specific edit.
- `scene_config.py` validates the root camera object.
- `pbrt_v4_art_studio.py` binds the Camera page to exact camera values.
- `render_snapshot.py` enforces the new root and rejects the obsolete location
  before a frozen render can proceed.
- Snapshot, configuration, builder, terrain-placement, and Qt tests provide
  the regression boundary.

### Progress record

- Verified a clean worktree on branch `pbrt-v4-art-studio`, synchronized with
  GitHub at `0e77a3e` before beginning Stage 2.
- Moved the live camera values to `camera_settings`, inserted the explicit
  existing `perspective` type, and removed `scene.camera`.
- Updated PBRT emission and terrain-detail placement to consume the same root
  camera object. No camera values are duplicated beneath `scene`.
- Updated the Qt Camera page to expose enabled state, type, eye, look target,
  up vector, and field of view from `camera_settings`.
- Expanded validation to enforce the approved perspective-camera contract:
  explicit boolean enabled state, supported type, finite three-component
  vectors, different eye/look points, nonzero and nonparallel up vector, and a
  finite field of view strictly between zero and 180 degrees.
- Added render-boundary rejection of obsolete `scene.camera` and began updating
  test fixtures and formatting-preserving save checks to the new root.
- Completed the fixture and regression migration. No operational read of
  `scene.camera` remains; remaining occurrences are rejection tests,
  validation messages, and historical migration documentation.
- Focused camera/configuration/snapshot/builder/placement/Qt verification ran
  54 tests: 52 passed and two composite tests were skipped because `.venv`
  intentionally lacks NumPy/Pillow.
- The complete `.venv` suite ran 90 tests: 83 passed and seven
  dependency-aware tests were skipped. The explicit system-Python non-GUI
  suite passed all 78 tests, including NumPy/Pillow-backed coverage.
- Live validation reports zero errors. Python byte-compilation, shell syntax,
  and `git diff --check` all pass.

### Exact Stage 2 migration audit

A mechanical comparison starts from `0e77a3e`, removes only `scene.camera`,
inserts the same values at root `camera_settings`, and exposes the builder's
existing `perspective` type. It reports:

```text
stage_two_only True
root_order ['file_names', 'file_paths', 'camera_settings', 'runtime', 'pipeline', 'scene']
scene_has_camera False
```

### Stage 2 structural PBRT comparison

The archived `020525` configuration was migrated through Stages 1 and 2 in
memory and built with the current builder in a temporary `/tmp` workspace. No
second scene JSON was written and PBRT was not launched. The first attempt used
`.venv` and stopped before generation because that environment intentionally
lacks NumPy. The system-Python rerun completed in approximately 25 seconds.

The emitted scene and the archived pre-migration PBRT file are identical:

```text
pre-migration size:  117,462,947 bytes
Stage 2 size:        117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The temporary comparison directory was removed after verification. The live,
gitignored generated scene was not rebuilt or altered.

### Stage 2 result

All Stage 2 acceptance requirements are satisfied. The next approved stage is
the exact move of film, sampler, integrator, backend, and shaft-compositing
controls into root `render_settings`.

## Stage 3 — render settings

Status: implementation and validation complete from pushed Stage 2 checkpoint
`184eb02`

### Exact target and value mapping

The approved root `render_settings` block owns film, sampler, integrator,
backend, and shaft-compositing controls. Current values move as follows:

- `scene.film.x_resolution/y_resolution` move unchanged; the currently true
  `enabled` switch is removed because film emission is a required render phase.
- `scene.sampler.type/pixel_samples` move unchanged; its currently true
  `enabled` switch is removed for the same reason.
- `scene.integrator.type/max_depth` move unchanged; its currently true
  `enabled` switch is removed.
- `runtime.use_gpu: true` becomes `render_settings.backend.type: "gpu"` and
  `runtime.show_stats` becomes `backend.show_statistics` unchanged.
- `pipeline.shaft_composite` moves unchanged beneath `render_settings`.
- `pipeline.build_scene.enabled`, currently true, is removed because building
  from frozen inputs is mandatory behavior rather than an artistic option.
- The obsolete `runtime` and `pipeline` roots are removed completely.

### Consumer inventory

- `render_pipeline.sh` owns mandatory building, CPU/GPU flags, statistics, and
  ordinary-versus-composite workflow selection.
- `render_shaft_composite.py` consumes backend flags and all pass/compositing
  controls.
- `scene_workspace/build_scene.py` emits film, sampler, and integrator PBRT and
  passes film dimensions to camera-frustum placement.
- `render_snapshot.py` previously supported the obsolete optional-build switch
  when deciding whether to copy prebuilt generated files.
- `scene_config.py` and the Qt Render page validate and expose exact render
  values.
- Snapshot/pipeline, composite, builder, placement, configuration, and Qt tests
  form the regression boundary.

The standard pipeline must honor `shaft_composite.enabled` without reading
mutable live settings after snapshot creation. It will freeze inputs first,
then dispatch the frozen composite script and frozen config when enabled.

### Progress record

- Inserted `render_settings` after `camera_settings` in the sole live JSON and
  moved every approved value without changing its artistic or numeric meaning.
  Removed the obsolete `runtime` and `pipeline` roots and the old render blocks
  beneath `scene`; no compatibility copies or fallback readers remain.
- Made scene construction mandatory in the standard immutable pipeline. CPU or
  GPU selection, statistics, and ordinary-versus-composite dispatch are read
  from the frozen `render_settings` before an expensive scene build begins.
- Connected the enabled composite workflow to the already-created frozen
  transaction, so it uses the same timestamp, source mirror, and frozen JSON
  instead of snapshotting mutable live settings a second time.
- Updated the standard builder to emit required film, Halton sampler, and
  volume-path integrator directives from `render_settings`, and to pass the
  migrated film dimensions to terrain-detail camera-frustum placement.
- Updated the direct composite entry point, immutable snapshot boundary,
  validator, and Qt Render page. Direct builder and composite calls now reject
  unsupported backend, non-boolean statistics, invalid light references,
  negative composite controls, unsupported sampler/integrator types, and
  invalid render dimensions before doing render work.
- Updated pipeline, snapshot, composite, builder, configuration, and Qt tests,
  plus the shaft-compositing operator documentation. An operational search
  found no remaining live reads of the obsolete render paths.
- Focused virtual-environment verification ran 55 tests: 51 passed and four
  NumPy/Pillow-dependent tests were skipped. The matching system-Python subset
  passed all 42 tests, including the composite coverage.
- The complete `.venv` suite ran 98 tests: 89 passed and nine dependency-aware
  tests were skipped. System Python passed all 85 non-GUI tests.
- Live validation reports zero errors. Python byte-compilation, shell syntax,
  and `git diff --check` all pass.

### Exact Stage 3 migration audit

A mechanical comparison starts from `184eb02`, applies only the approved value
moves and removals, and compares that result with the sole live JSON. It
reports:

```text
stage_three_only True
root_order ['file_names', 'file_paths', 'camera_settings', 'render_settings', 'scene']
obsolete_roots_present []
obsolete_scene_fields_present []
```

### Stage 3 structural PBRT comparison

The archived `020525` configuration was migrated through Stages 1–3 entirely
in memory and built with the current builder in a temporary `/tmp` workspace.
No second scene JSON was created and PBRT was not launched. The emitted scene
is byte-for-byte identical to the pre-migration artifact:

```text
pre-migration size:  117,462,947 bytes
Stage 3 size:        117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The temporary comparison directory was removed. The live, gitignored generated
scene was not rebuilt or altered, and no production render was launched.

### Stage 3 result

All Stage 3 acceptance requirements are satisfied. The next approved stage is
to establish the `scene_description` shell with `mode`, the migrated scene
name, and `scene_context`, while continuing to keep only one authoritative
configuration.

## Stage 4 — scene description shell and context

Status: implementation and validation complete from pushed Stage 3 checkpoint
`9e91e65`

### Exact target and bounded scope

Stage 4 inserts this root immediately after `render_settings`:

```json
"scene_description": {
  "mode": "new",
  "name": "Poppy Field Overcast 8AM Study",
  "scene_context": {
    "date": "2026-06-21",
    "local_time": "08:00:00",
    "time_zone": "America/New_York",
    "latitude": 43.0,
    "longitude": -76.0,
    "world_north": [0.0, 0.0, 1.0]
  }
}
```

The existing `scene.name` value moves once to `scene_description.name` and the
old path is removed. The six approved context values are explicit new metadata
that will affect lighting only after a later sky/sun stage adds
`use_astronomical_direction`; current explicit light directions remain
unchanged.

The remaining legacy `scene` object deliberately stays beside the new shell
for now. Landforms, independent objects, sky, atmosphere, and water move in
their later approved stages, one complete subsystem at a time. Creating empty
placeholder modules in `scene_description` now would duplicate those still-live
concepts, so Stage 4 does not do that.

### Consumer inventory

- `render_pipeline.sh` displays the migrated name from the frozen JSON.
- `render_snapshot.py` derives archive names and manifest metadata from
  `scene_description.name`, validates the complete shell/context contract, and
  rejects obsolete `scene.name` before a render can proceed.
- `scene_workspace/build_scene.py` uses the migrated name in the PBRT header and
  direct-builder progress output while continuing to read not-yet-migrated
  scene modules from the temporary legacy root.
- `scene_config.py` validates mode, name, ISO date/time, IANA time zone,
  latitude, longitude, and nonzero horizontal world north, and rejects the old
  name path.
- The Qt Scene page exposes every shell and context value through the sole live
  JSON, while its summary reports the active name, mode, time, and location.
- Snapshot, pipeline, formatting-preserving configuration, direct builder, and
  offscreen Qt tests form the regression boundary.

### Progress and verification record

- Verified a clean synchronized `pbrt-v4-art-studio` worktree at `9e91e65`
  before beginning Stage 4.
- Added only the approved `scene_description` shell/context and moved the live
  name without altering any current landform, object, sky, atmosphere, water,
  camera, render, file, or path value.
- Removed all operational reads of `scene.name`; remaining occurrences are
  rejection tests, migration maps, and historical documentation.
- Focused `.venv` verification ran 60 tests: 56 passed and four
  NumPy/Pillow-dependent tests were skipped. The matching system-Python subset
  passed all 46 tests.
- The complete `.venv` suite ran 102 tests: 93 passed and nine
  dependency-aware tests were skipped. System Python passed all 88 non-GUI
  tests.
- Live validation reports zero errors. Python byte-compilation, shell syntax,
  and `git diff --check` all pass.

### Exact Stage 4 migration audit

A mechanical comparison starts from `9e91e65`, removes only `scene.name`, and
inserts that same value plus the approved context at the new root. It reports:

```text
stage_four_only True
root_order ['file_names', 'file_paths', 'camera_settings', 'render_settings', 'scene_description', 'scene']
scene_name_present False
scene_description_keys ['mode', 'name', 'scene_context']
```

### Stage 4 structural PBRT comparison

The archived `020525` configuration was migrated through Stages 1–4 entirely
in memory and built with the current builder in a temporary `/tmp` workspace.
No second scene JSON was written and PBRT was not launched. The emitted scene
is byte-for-byte identical to the pre-migration artifact:

```text
pre-migration size:  117,462,947 bytes
Stage 4 size:        117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The temporary comparison directory was removed automatically. The live,
gitignored generated scene was not rebuilt or altered, and no production render
was launched.

### Stage 4 result

All Stage 4 acceptance requirements are satisfied. The next approved work is
Stage 5: migrate landforms and their surface objects one complete generator at
a time, beginning with a fresh exact ownership and consumer inventory.

## Stage 5A — foreground landform core

Status: implementation and validation complete from pushed Stage 4 checkpoint
`856d84d`

### Exact target and bounded scope

Stage 5A moves the two foreground terrain profiles and their shared rendered
surface into the approved landform-first structure. It deliberately does not
move grass, poppies, litter, rocks, undergrowth, the vista plane, or distant
hills. Those generators retain one temporary live location until their own
one-at-a-time substages.

The new ownership for each retained terrain alternative is:

- profile name -> `scene_description.landforms[].name`;
- old module/profile selection -> independent `enabled` values;
- `center` plus `base_height` -> `placement.position`;
- `size` and `resolution` -> the named plane patch's `dimensions` and
  `subdivisions`;
- `slope`, `noise`, and optional `right_profile` ->
  `topography.parameters` under generator `terrain_heightfield`;
- the old shared ground material and surface texture -> each independent
  landform's `surface.material` and `surface.texture`;
- an explicit empty `surface_objects` array, reserved for later Stage 5B moves.

`flat_landform` is enabled because it was the selected live terrain;
`right_dip_rise` remains present and independently disabled. Copying the shared
material and texture into both new independent objects is intentional ownership,
not an old/new compatibility duplicate: either retained landform remains a
complete usable authored alternative.

After the move, the only child of temporary `scene.landscape.ground` is
`details`, and its keys are exactly `grass`, `poppies`, `litter`, `rocks`, and
`undergrowth`. The obsolete `ground.enabled`, `ground.active_landform`,
`ground.landforms`, `ground.material`, and `ground.details.surface` keys are
absent.

### Consumer inventory and implementation

- `terrain.py` now translates one enabled `terrain_heightfield` landform and
  its enabled plane patch into the existing deterministic `RollingHillside`
  implementation. Position and local-position offsets are applied explicitly;
  nonzero rotations are rejected rather than silently ignored.
- `scene_workspace/build_scene.py` locates exactly one enabled foreground
  terrain landform, reads its material and texture from `surface`, and continues
  passing the temporary detail-only ground block to not-yet-migrated generators.
- `scene_config.py` validates names, enable switches, placement vectors, named
  plane patches, dimensions, subdivisions, topography registration, surface
  ownership, surface-object arrays, uniqueness, the sole enabled terrain
  invariant, and the absence of old core paths.
- `render_snapshot.py` enforces the same stage boundary before freezing a
  render, including rejection of obsolete ground ownership and missing or
  ambiguous enabled terrain.
- `render_shaft_composite.py` applies terrain reflectance scaling at the new
  landform surface while preserving the same terrain scaling for legacy surface
  objects until each object moves.
- The Qt Ground page edits the active landform's surface texture. The Landform
  page exposes both independent entries, their enable values, placement,
  dimensions, grade, and noise amplitude without the removed selector.
- `scene_workspace/flat_landform_preview.py` uses the new landform entry while
  retaining its intentionally bounded legacy detail preview input.
- Terrain, snapshot, shaft-composite, formatting-preserving config, live-config,
  and offscreen Qt tests cover the new boundary.

### Mechanical Stage 5A ownership audit

A mechanical transformation starts from `856d84d`, performs only the approved
mapping above, and compares the complete parsed result with the live JSON. It
reports:

```text
stage5a_only True
landform_names ['right_dip_rise', 'flat_landform']
enabled_landforms ['flat_landform']
legacy_ground_keys ['details']
legacy_detail_keys ['grass', 'poppies', 'litter', 'rocks', 'undergrowth']
```

### Structural-build diagnosis and exact comparison

The first full-current-config build was intentionally isolated under `/tmp` and
did not launch PBRT. It emitted about 1.044 GB rather than matching the
117,462,947-byte `020525` diagnostic artifact. Inspection showed that the new
file contained today's enabled 3,400,000 grass instances, while the archived
`020525` configuration used for every earlier migration proof had grass
disabled and bounded render settings. This was an invalid comparison between
different inputs, not a terrain migration divergence. The temporary 1.044 GB
file was removed.

The comparison was rerun by migrating the archived `020525` input through
Stages 1–5A entirely in memory and building it with the current builder in a
fresh temporary workspace. No second scene JSON was written and PBRT was not
launched. The result is byte-for-byte identical:

```text
pre-migration size:  117,462,947 bytes
Stage 5A size:       117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

Both temporary structural-build directories were removed. The live accepted
artifact and the live generated PBRT file were not modified.

### Tests and checks

- Focused `.venv` verification ran 63 tests: 59 passed and four
  NumPy/Pillow-dependent tests were skipped.
- The complete `.venv` suite ran 108 tests: 99 passed and nine
  dependency-aware tests were skipped.
- System Python passed all 94 non-GUI tests.
- The live JSON validates with zero errors; JSON parsing, Python byte
  compilation, operational old-path search, and `git diff --check` pass.
- No production PBRT render was launched.

### Stage 5A result

The foreground landform core is fully migrated with no live old/new ownership
bridge. Stage 5B proceeds through surface-object generators individually,
beginning with grass, while preserving exact generator parameters and rendered
behavior at each checkpoint.
