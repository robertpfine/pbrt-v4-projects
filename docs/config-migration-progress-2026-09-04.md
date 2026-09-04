# Live Configuration Migration Progress — 2026-09-04

Status: Stages 1–6 implementation and validation complete

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

The Stage 5A commit is `302376f` (`Migrate foreground landform core`). It was
pushed to `origin/pbrt-v4-art-studio`, and the required continuity copy to
`gdrive:wipImages/pbrt-v4/SessionArchive/continuity.md` succeeded immediately.

## Stage 5B.1 — grass surface-object generator

Status: implementation and validation complete from pushed Stage 5A checkpoint
`302376f`

### Exact ownership move

The sole legacy `scene.landscape.ground.details.grass` object moved to the
enabled `flat_landform.surface_objects[]` array as:

```text
name:       grass
enabled:    preserved true
generator:  grass
construction:
  blade, tuft, surface, reflectance_variants
population:
  seed, variants, layers, region, max_slope_degrees, y_offset,
  exclusion, camera_frustum, extension
```

Nested layer seed/scale/patchiness, blade tropism and spatial field, coating
values, frustum bottom margin/depth fade, and the disabled distant-hill
extension all retain their exact field names and values. No grass value remains
at the old path; the other four detail generators are unchanged.

### Consumers and safeguards

- The scene builder resolves at most one `grass` generator on the enabled
  terrain landform and flattens its adjacent `construction` and `population`
  objects only for the existing generator implementation. An absent grass
  object remains a valid grass-free scene; duplicates are rejected.
- Terrain detail output and dormant distant-hill grass extension both consume
  that same resolved object, so there is no hidden second definition.
- Configuration validation checks unique surface-object names/generators,
  construction/population objects, grass material type, depth-fade structure,
  and population layer/count, and rejects the obsolete legacy path.
- The immutable snapshot boundary rejects legacy grass ownership before a
  render can be frozen.
- The Qt Grass page and scene summary use the new construction/population paths.
- The shaft pass resets and terrain-scales the migrated grass together with the
  owning terrain surface, preserving its pre-migration composite behavior.
- The local-only ignored flat-landform preview helper was adjusted to resolve
  migrated grass without adding a second configuration.

### Mechanical ownership audit

A mechanical transformation starts from `302376f`, removes only the legacy
grass object, partitions its fields according to the approved mapping, and
appends the result to the enabled terrain landform. The complete parsed JSON
comparison reports:

```text
stage5b_grass_only True
owner flat_landform
construction_keys ['blade', 'tuft', 'surface', 'reflectance_variants']
population_keys ['seed', 'variants', 'layers', 'region',
                 'max_slope_degrees', 'y_offset', 'exclusion',
                 'camera_frustum', 'extension']
legacy_detail_keys ['poppies', 'litter', 'rocks', 'undergrowth']
```

### Exact structural PBRT comparison

The archived `020525` configuration, whose grass generator is disabled, was
migrated through Stage 5B.1 entirely in memory and built in a temporary
workspace. The builder resolved the new grass object and preserved the disabled
state. PBRT was not launched and no second scene JSON was written.

```text
pre-migration size:  117,462,947 bytes
Stage 5B.1 size:     117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The temporary comparison directory was removed. The live generated scene and
archived artifact were not modified.

### Tests and result

- The complete `.venv` suite ran 111 tests: 102 passed and nine
  dependency-aware tests were skipped.
- System Python passed all 97 non-GUI tests.
- The live JSON validates with zero errors.
- No production PBRT render was launched.

Grass is fully migrated with no old/new compatibility ownership. The next
one-generator substage is poppies.

The grass commit is `975b731` (`Migrate grass surface object`) and is pushed to
`origin/pbrt-v4-art-studio`. Its single continuity-copy attempt immediately
failed with Google Drive `RATE_LIMIT_EXCEEDED`; per the artist's instruction,
it was not retried.

## Stage 5B.2 — poppy surface-object generator

Status: implementation and validation complete from pushed grass checkpoint
`975b731`

### Exact ownership move

The sole legacy `scene.landscape.ground.details.poppies` object moved directly
after grass under enabled `flat_landform.surface_objects[]` with generator
`poppy`.

`construction` contains every prior botanical/material field:

```text
stem_reflectance, foliage_reflectance, tropism, center_reflectance,
capsule_reflectance, anther_reflectance, stigma_reflectance,
stigma_center_reflectance, basal_blotch_reflectance,
basal_blotch_variants, color_names, center_reflectance_variants,
petal_transmittance, rim_transmittance, reflectance_variants
```

`population` contains every scatter/repetition field:

```text
count, seed, region, scale, camera_frustum, extension,
max_slope_degrees, patchiness, exclusion, y_offset, variants
```

All nested values—including seven color variants, reproductive-part colors,
stem/foliage tropism, flower-vs-root framing, depth fade, and the enabled
`broad_rise` extension—are unchanged. Litter, rocks, and undergrowth remain at
their single temporary paths.

### Consumers and safeguards

- The scene builder resolves and flattens the `poppy` surface object at the
  generator call. Foreground poppies and the distant-hill extension consume the
  same object.
- Configuration validation checks surface-object uniqueness plus poppy count,
  ascending scale, camera-frustum enable type, placement reference, and depth
  fade at the new population path, and rejects legacy poppy ownership.
- Render snapshotting rejects the obsolete ground-detail poppy path and malformed
  or duplicate new poppy ownership before rendering.
- The Qt Poppies page edits enabled, count, scale, frustum, and placement
  reference at the new paths; the scene summary reads the new population count.
- Shaft-pass reflectance scaling continues to treat poppies as terrain-owned
  surface objects.
- The local-only ignored flat-landform preview helper resolves migrated poppies
  without adding another configuration.

### Mechanical ownership audit

The complete parsed JSON comparison against a mechanical transformation of
`975b731` reports:

```text
stage5b_poppy_only True
owner flat_landform
surface_generators ['grass', 'poppy']
construction_keys ['stem_reflectance', 'foliage_reflectance', 'tropism',
                   'center_reflectance', 'capsule_reflectance',
                   'anther_reflectance', 'stigma_reflectance',
                   'stigma_center_reflectance',
                   'basal_blotch_reflectance', 'basal_blotch_variants',
                   'color_names', 'center_reflectance_variants',
                   'petal_transmittance', 'rim_transmittance',
                   'reflectance_variants']
population_keys ['count', 'seed', 'region', 'scale', 'camera_frustum',
                 'extension', 'max_slope_degrees', 'patchiness',
                 'exclusion', 'y_offset', 'variants']
legacy_detail_keys ['litter', 'rocks', 'undergrowth']
```

### Exact structural PBRT comparison

Archived `020525` was migrated through the poppy move entirely in memory and
built in a temporary workspace. Its disabled poppy state was resolved through
the new surface object. No second JSON was written and PBRT was not launched.

```text
pre-migration size:  117,462,947 bytes
Stage 5B.2 size:     117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The temporary comparison directory was removed; live and archived artifacts
were not modified.

### Tests and result

- The complete `.venv` suite ran 113 tests: 104 passed and nine skips.
- System Python passed all 99 non-GUI tests.
- Live JSON validation reports zero errors.
- No production PBRT render was launched.

Poppies are fully migrated with no old/new ownership bridge. Litter is next.

The poppy commit is `1a1a76d` (`Migrate poppy surface object`) and is pushed to
`origin/pbrt-v4-art-studio`. Its required continuity copy to Google Drive
succeeded immediately.

## Stage 5B.3 — litter surface-object generator

Status: implementation and validation complete from pushed poppy checkpoint
`1a1a76d`

The disabled legacy litter generator moved to the third surface-object entry
under enabled `flat_landform`. Its exact partition is:

```text
construction: variants, scale, reflectance_variants
population:   seed, count, region, max_slope_degrees, y_offset,
              patchiness, attraction
```

The builder resolves `generator: "litter"` through the same explicit
construction/population adapter used by the other migrated objects. Validation
checks nonnegative count and ascending construction scale; configuration and
snapshot boundaries reject the obsolete ground-detail litter path.

The mechanical parsed-JSON audit reports:

```text
stage5b_litter_only True
surface_generators ['grass', 'poppy', 'litter']
legacy_detail_keys ['rocks', 'undergrowth']
```

Archived `020525` was migrated entirely in memory and built in a temporary
workspace without launching PBRT or writing another JSON:

```text
pre-migration size:  117,462,947 bytes
Stage 5B.3 size:     117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The temporary directory was removed. The complete `.venv` suite ran 115 tests
(106 passed, nine skips), and system Python passed all 101 non-GUI tests. Live
JSON validation reports zero errors. Litter has no old/new ownership bridge;
rocks are next.

The litter commit is `b0faa40` (`Migrate litter surface object`) and is pushed
to `origin/pbrt-v4-art-studio`. Its required Google Drive continuity copy
succeeded immediately.

## Stage 5B.4 — rock-scatter surface-object generator

Status: implementation and validation complete from pushed litter checkpoint
`b0faa40`

The disabled `rocks` block moved to the fourth surface object under enabled
`flat_landform` and uses the approved `rock_scatter` generator name:

```text
construction: variants, scale, reflectance_variants
population:   seed, count, region, max_slope_degrees, y_offset,
              exclusion, patchiness
```

The builder resolves that generator into the existing `rocks` detail layer;
validation checks nonnegative count and ascending construction scale, and both
configuration and snapshot boundaries reject the old path.

Mechanical ownership audit:

```text
stage5b_rocks_only True
surface_generators ['grass', 'poppy', 'litter', 'rock_scatter']
legacy_detail_keys ['undergrowth']
```

Archived `020525` was migrated in memory and built without launching PBRT:

```text
pre-migration size:  117,462,947 bytes
Stage 5B.4 size:     117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The comparison itself completed normally. Deleting its temporary directory
then stalled within the filesystem tool call for roughly ten minutes before
completing; no renderer was active, and no live or archived artifact changed.
Future comparison and cleanup calls are kept separate so cleanup latency cannot
hide a completed result.

The complete `.venv` suite ran 117 tests (108 passed, nine skips); system Python
passed all 103 non-GUI tests. Live validation reports zero errors. Rocks have no
old/new ownership bridge; undergrowth is next.

The rock-scatter commit is `97c5a7c` (`Migrate rock scatter surface object`) and
is pushed to `origin/pbrt-v4-art-studio`. Its single Google Drive continuity
attempt immediately rate-limited and was not retried.

## Stage 5B.5 — undergrowth and legacy-ground removal

Status: implementation and validation complete from pushed rock checkpoint
`97c5a7c`

Disabled undergrowth moved to the fifth surface object under enabled
`flat_landform`:

```text
construction: variants, scale, reflectance_variants
population:   seed, count, region, max_slope_degrees, y_offset,
              exclusion, patchiness
```

This was the final child of temporary `scene.landscape.ground.details`.
Consequently, the migration removes the now-empty complete
`scene.landscape.ground` wrapper, its path constant/import, and builder and
shaft-composite dependencies. The builder now assembles all five terrain-detail
inputs solely from the enabled landform's surface objects. Configuration and
snapshot validation reject the complete obsolete ground wrapper as well as
specific old child paths for useful diagnostics.

Mechanical ownership audit against `97c5a7c`:

```text
stage5b_undergrowth_only True
surface_generators ['grass', 'poppy', 'litter', 'rock_scatter', 'undergrowth']
legacy_ground_present False
```

Archived `020525` was migrated in memory and built in an isolated temporary
workspace without a second JSON or PBRT launch:

```text
pre-migration size:  117,462,947 bytes
Stage 5B.5 size:     117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The comparison completed normally. The separately invoked temporary cleanup
took about 95 seconds in the filesystem layer, confirming the prior delay was
cleanup latency rather than a render or generator loop.

The complete `.venv` suite ran 119 tests (110 passed, nine skips); system Python
passed all 105 non-GUI tests. Live validation reports zero errors. No production
render was launched. Stage 5B is complete; Stage 5C begins with the vista plane.

The undergrowth commit is `9b4666f` (`Migrate undergrowth surface object`) and
is pushed to `origin/pbrt-v4-art-studio`. Its single Google Drive continuity
attempt immediately rate-limited and was not retried.

## Stage 5C.1 — vista-plane landform

Status: implementation and validation complete from pushed Stage 5B checkpoint
`9b4666f`

The enabled `vista_plane` moved atomically from `scene.geometry[]` to a third
independent entry in `scene_description.landforms`. The new ownership is:

```text
placement.position:                 [-9000, -250, -12000]
geometry.patches[0].generator:      plane
geometry.patches[0].dimensions:     [50000, 50000]
geometry.patches[0].subdivisions:   [2, 2]
geometry.patches[0].local_position: [0, -500, 0]
topography.enabled:                 false
surface.material:                   diffuse reflectance + reflectance_scale
surface.texture.generator:          vista_surface_mottle
surface_objects:                    []
```

Every former mottle control moved intact beneath `surface.texture`: resolution,
seed, cluster size/floor, mottle and fine sizes, coverage, softness, contrast,
mottle/accent reflectances, and accent fraction. The builder adapts the planar
landform to the established generic geometry writer at the original output
location. This preserves the old bilinear-mesh point ordering, transform,
material multiplication, generated texture, automatic UVs, and PBRT comments
without keeping duplicate configuration ownership.

Configuration and snapshot validation reject an old `scene.geometry[]` entry
labeled `vista_plane`. Topography validation now accepts the approved explicit
`{"enabled": false}` form for a flat landform rather than requiring a dormant
terrain generator. The Qt Landform page enumerates the new entry without
assuming that it has heightfield grade and noise controls.

Mechanical ownership audit:

```text
enabled_landforms ['flat_landform', 'vista_plane']
vista_patch_generators ['plane']
vista_texture_generator vista_surface_mottle
legacy_geometry_vista_count 0
```

For the exact structural proof, the current migrated configuration was adjusted
in memory with the seven known `020525` diagnostic differences from the
pre-migration live configuration: 640-by-464 film, eight samples, max depth 20,
disabled grass and poppies, Python cloud-grid backend, and the former disabled
remote sync (which has no builder effect). No second JSON was written and PBRT
was not launched.

```text
pre-migration size:  117,462,947 bytes
Stage 5C.1 size:     117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The comparison completed normally. Its temporary directory was deleted in a
separate filesystem call after the result was recorded. The complete `.venv`
suite ran 122 tests (113 passed, nine skips); system Python passed all 108
non-GUI tests. Live validation reports zero errors. No production render was
launched. Stage 5C continues with the retained `broad_rise` distant landform.

The vista-plane commit is `921ef94` (`Migrate vista plane landform`) and is
pushed to `origin/pbrt-v4-art-studio`. Its required Google Drive continuity
copy succeeded immediately.

## Stage 5C.2 — distant-ridge landform

Status: implementation and validation complete from pushed vista checkpoint
`921ef94`

The retained `broad_rise` moved atomically out of
`scene.landscape.distant_hills.layers[]` and became an independent disabled
landform. The former module-level disabled state and enabled child state
collapse into the one meaningful landform switch, `enabled: false`, preserving
the accepted hill-disabled scene without retaining competing switches.

```text
placement.position:                 center X/Z + base elevation Y
placement.rotation_degrees:         prior ground-plane rotation on Y
geometry.patches[0]:                plane dimensions + mesh subdivisions
topography.generator:               distant_ridge
topography.parameters:              ridge height, cross-section, peaks, noise
surface.material:                   diffuse reflectance + reflectance_scale
surface.texture.enabled:            false
surface_objects:                    []
```

`distant_hills.configured_distant_hills()` translates the new landforms into
the established deterministic `DistantHillLayer` input. The scene builder uses
only this new ownership; the old landscape wrapper is absent. Grass and poppy
extensions continue targeting the stable name `broad_rise`. Configuration and
snapshot validation accept and inspect `distant_ridge` landforms and reject the
old wrapper. The Qt inspector now edits landform placement, plane-patch size,
ridge parameters, material, and the landform's single enable switch directly.
The scene summary derives its hill status from distant-ridge landforms.

Mechanical ownership audit:

```text
distant_ridge_names ['broad_rise']
enabled_distant_ridges []
broad_rise_patch_generators ['plane']
legacy_distant_hills_present False
landscape_keys ['water']
```

The archived `020525` diagnostic migration was built in memory with no second
JSON and no PBRT launch:

```text
pre-migration size:  117,462,947 bytes
Stage 5C.2 size:     117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

To honor the artist's instruction not to trigger another keyboard approval for
temporary cleanup while unattended, the isolated proof workspace is retained
at `/tmp/pbrt-ridge-stage5c.igR9p4`. It contains only the generated diagnostic
scene and texture output.

The complete `.venv` suite ran 125 tests (116 passed, nine skips); system Python
passed all 111 non-GUI tests. Live validation reports zero errors. No production
render was launched. Stage 5C is complete; Stage 6 begins with independent
objects.

The distant-ridge commit is `d4ce2ff` (`Migrate distant ridge landform`) and is
pushed to `origin/pbrt-v4-art-studio`. Its single Google Drive continuity
attempt immediately rate-limited and was not retried.

## Stage 5D.1 — L-system tree surface objects

Status: implementation and validation complete from pushed distant-ridge
checkpoint `d4ce2ff`

The Stage 6 inventory exposed a required ordering correction: the resolved
schema classifies trees as landform surface objects, not independent objects.
Therefore Stage 5D completes the remaining landform-owned generator families
before `scene_description.objects` begins.

Both entries from `scene.lsystem_trees[]` moved in stable order beneath enabled
`flat_landform.surface_objects[]`:

```text
name          generator      enabled  construction.preset
live_oak      lsystem_tree   false    live_oak
fractal_tree  lsystem_tree   true     fractal_tree
```

Every geometry, recursion, balance, growth, crownlet, seed, debug-render,
scale, and reflectance field moved beneath each object's `construction`.
`population` owns `method: "explicit"`, origin, explicit terrain-placement
state, and the ordered instance array. Neutral live-oak scale, terrain
placement, and empty instances are now explicit instead of relying on builder
fallbacks. The active fractal tree retains its three manually placed horizon
instances exactly.

The builder's plural surface-object resolver preserves source order and feeds
the existing L-system writer without a legacy path. Configuration validation
supports multiple named objects using the same registered generator, validates
the construction/population split and placements, and rejects
`scene.lsystem_trees`. Snapshot validation and the Qt tree inspector use the new
path; the inspector temporarily continues to include the not-yet-migrated
space-colonization entries until Stage 5D.2.

Mechanical ownership audit:

```text
lsystem_tree_names ['live_oak', 'fractal_tree']
enabled_lsystem_trees ['fractal_tree']
fractal_instance_count 3
legacy_lsystem_trees_present False
```

The archived `020525` diagnostic migration was built in memory without a second
JSON or PBRT launch:

```text
pre-migration size:  117,462,947 bytes
Stage 5D.1 size:     117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The retained proof workspace is `/tmp/pbrt-lsystem-stage5d.QSTghk`; leaving it
in `/tmp` avoids another destructive-cleanup keyboard prompt while the artist
is away. The complete `.venv` suite ran 128 tests (119 passed, nine skips);
system Python passed all 114 non-GUI tests. Live validation reports zero errors.
No production render was launched. Stage 5D.2 migrates space-colonization trees
and folds the separate grove population into its selected tree.

The L-system tree commit is `9f60e2a` (`Migrate L-system tree surface objects`)
and is pushed to `origin/pbrt-v4-art-studio`. Its single Google Drive continuity
attempt immediately rate-limited and was not retried.

## Stage 5D.2 — space-colonization trees and grove population

Status: implementation and validation complete from pushed L-system checkpoint
`9f60e2a`

Both disabled entries from `scene.trees[]` moved in stable order beneath
`flat_landform.surface_objects[]` with generator `space_colonization_tree`.
Their complete growth, attraction, thickening, topology, material, and foliage
controls moved to `construction`. Root placement and explicit instances moved
to `population`.

The separate disabled `scene.grove` block selected tree index zero. Its seven
ordered placements are therefore now owned by
`space_colonization_tree_1.population.instances`, whose explicit `enabled:
false` retains the dormant grove state. The second tree owns an explicit empty
placement list. The old `scene.trees` and `scene.grove` paths are absent.

The existing tree writer and standalone `generate.py` orchestrator flatten the
new construction/population boundary in stable source order, preserving
generated filenames and PBRT object indices. `render_pipeline.sh` checks the
new generator and nested foliage path. Configuration and snapshot validation
reject both old paths. The Qt tree inspector now enumerates only landform-owned
L-system and space-colonization objects. A lazy generator import keeps the new
configuration-routing helper testable without loading optional numerical tree
dependencies when no tree generation is requested.

Two focused failures were found and resolved before the proof: snapshot legacy
path validation reused the variable holding the scene name, causing archive
names to become `grove`, and the frozen-pipeline integration fixture still
inserted an empty old `scene.trees` array. The variable and fixture were
corrected, and the frozen-render integration passed afterward.

Mechanical ownership audit:

```text
space_tree_names ['space_colonization_tree_1', 'space_colonization_tree_2']
enabled_space_trees []
population_instance_enabled [False, False]
population_placement_counts [7, 0]
legacy_trees_present False
legacy_grove_present False
```

The archived `020525` diagnostic migration was built in memory without a second
JSON or PBRT launch:

```text
pre-migration size:  117,462,947 bytes
Stage 5D.2 size:     117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The proof workspace remains at `/tmp/pbrt-space-tree-stage5d.xCB0Af` to avoid a
destructive cleanup prompt while unattended. The complete `.venv` suite ran
132 tests (123 passed, nine skips); system Python passed all 118 non-GUI tests.
Live validation reports zero errors, and `render_pipeline.sh` passes `bash -n`.
No production render was launched. Stage 5D is complete; Stage 6 begins with
independently placed objects.

## Stage 6.1 — planar-phyllotaxis independent object

Status: implementation and validation complete from pushed landform checkpoint
`857d13b`

The disabled `sunflower_head_vogel_pattern` moved atomically from
`scene.planar_phyllotaxis[]` to the first entry in
`scene_description.objects[]`. The independent object now owns its descriptive
name, enabled state, explicit neutral position and rotation, registered
`planar_phyllotaxis` geometry source, composite-generator material boundary,
and complete construction. Every existing count, Vogel spacing/divergence,
absolute head center, pitch, dome surface, receptacle, underside, bract, stem,
leaf, zoned organ, and nested material value remains intact beneath
`construction`; there is no duplicate live configuration.

The scene builder resolves registered independent objects and flattens the new
boundary into the established phyllotaxis writer in stable array order. Object
placement is operational: non-neutral transforms wrap the generated object,
while the migrated neutral transform emits no extra PBRT directives. The shaft
composite now scales independent-object reflectances with other visible
surfaces. Configuration validation and immutable-snapshot validation require
names, enabled flags, finite three-component placement vectors, one and only
one geometry source, material ownership, and generator construction; both
reject the removed `scene.planar_phyllotaxis` path.

The Qt Art Studio now includes an Independent Objects inspector. It exposes the
selected object's enabled state, geometry source, position, and rotation; its
dynamic placement bindings were verified before adding later volume objects so
the selector cannot silently edit the first entry. Generator-specific detail
remains directly editable in the sole authoritative JSON.

Mechanical ownership audit:

```text
object_names                       ['sunflower_head_vogel_pattern']
object_geometry_sources            ['planar_phyllotaxis']
enabled_objects                    []
legacy_planar_phyllotaxis_present  False
```

The archived `020525` diagnostic migration was built in memory without a
second JSON or PBRT launch:

```text
pre-migration size:  117,462,947 bytes
Stage 6.1 size:      117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The proof workspace remains at `/tmp/pbrt-phyllotaxis-stage6.SAmXb0`; it is
intentionally retained to avoid a destructive-cleanup approval prompt during
unattended work. The complete `.venv` suite runs 135 tests (126 passed, nine
dependency-aware skips), and system Python passes all 120 non-GUI tests. Live
validation reports zero errors, and `render_pipeline.sh` passes `bash -n`. No
production render was launched. Stage 6.2 migrates the disabled legacy
`volume_sphere` and `volume_box` into self-contained independent objects; the
legacy direct-grid construction will move with them, while `fog_volume` waits
for the atmosphere stage.

## Stage 6.2 — self-contained legacy volume objects

Status: implementation and validation complete from pushed Stage 6.1
checkpoint `93e199d`

The disabled `volume_sphere` and `volume_box` moved in their stable order from
`scene.geometry[]` into `scene_description.objects[]` after the phyllotaxis
sunflower. The sphere explicitly selects native PBRT `pbrt_shape: "sphere"`
with radius parameters. The box explicitly selects the registered Art Studio
`generator: "box"`, with its six retained bounds under `construction`. Both
objects own their interface material, explicit position and rotation, and a
complete interior/exterior medium definition.

The former shared disabled `scene.grid` and `scene.zones` configuration was
copied in full into each boundary's `medium.interior`, as required by the
approved self-contained-volume design, and both shared paths were removed.
Each object has a distinct configured medium name while preserving all former
resolution, axis, absorption, bounds, emission, two noise layers, and four
spectral-zone values. Object enabled state replaces the old grid switch. The
remaining `scene.geometry[]` contains only disabled `fog_volume`; it is
intentionally retained until the fog object absorbs its boundary in Stage 8.

The dependency-free `scene_objects.py` now routes generated objects, native/box
boundary geometry, and enabled object-owned rgbgrid media. Separating this
logic also removed a test-order dependency in which a focused adapter test
could import NumPy-heavy scene-builder modules only after another test had
installed dependency stubs. The immutable snapshot already freezes every root
Python source, so the new routing module is included without a special case.
The existing builder writes one pre-world medium include containing each
enabled object's distinct declaration, then emits independent boundaries ahead
of the retained fog boundary in the original relative order.

Configuration and snapshot validation now reject old grid/zones and sphere/box
geometry ownership. They validate supported native/generated shapes, box
bounds, sphere radius, object placement, material, and the self-contained
rgbgrid medium shell. A focused 1×1×1 writer test verifies that the configured
owned name—not the former global `rgb_vol` name—is emitted. The Qt object
selector exposes all three independent objects and retains dynamic placement
binding.

Mechanical ownership audit:

```text
object_order          ['sunflower_head_vogel_pattern', 'volume_sphere', 'volume_box']
enabled_objects       []
legacy_geometry       ['fog_volume']
legacy_grid_present   False
legacy_zones_present  False
volume_sphere grid/zones preserved  True / True
volume_box grid/zones preserved     True / True
```

The archived `020525` diagnostic migration was built in memory without a
second JSON or PBRT launch:

```text
pre-migration size:  117,462,947 bytes
Stage 6.2 size:      117,462,947 bytes
both SHA-256:        c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result:          identical
```

The proof workspace remains at `/tmp/pbrt-volumes-stage6.FczgRq` to avoid an
unattended destructive-cleanup prompt. The complete `.venv` suite runs 139
tests (130 passed, nine dependency-aware skips), and system Python passes all
124 non-GUI tests. Live validation reports zero errors,
`render_pipeline.sh` passes `bash -n`, and the authoritative JSON parses
cleanly. No production render was launched. Stage 6 is complete; Stage 7 begins
with the sky background and sun before migrating each cloud as a self-contained
sky object.

## Stage 7.1 — sky shell, sun, and light shafts

Status: implementation and validation complete from pushed Stage 6 checkpoint
`9f2f9b5`

The complete legacy sky shell moved from `scene.sky` to
`scene_description.sky`. Its background is unchanged. The active labeled
`morning_sun` moved out of `scene.lights[]` to the singular `sky.sun` object;
its enabled state, PBRT distant type, from/to direction, blackbody temperature,
and scale are unchanged, and `use_astronomical_direction: false` explicitly
preserves manual direction. The dormant `shaft_sun` and complete
`sun_aperture` moved intact to `sun.light_shafts.light` and `.aperture`.
Rejected disabled point/spot experiments were removed from the live config and
remain recoverable in Git history. Old `scene.sky`, `scene.lights`, and
`scene.sun_aperture` are absent and rejected.

The builder reconstructs the established PBRT light order from the new
ownership. Cloud building, snapshot executable freezing, Qt sky/lighting
controls, description output, shaft base/isolated-pass configuration, and
shaft-option validation all read the new path. The legacy shared cloud shell
moved without internal changes in this substage; Stage 7.2 makes each cloud
self-contained.

Value and structural audit:

```text
background preserved       True
cloud shell preserved      True
morning sun preserved      True
shaft light preserved      True
aperture preserved         True
legacy sky/light keys      []
pre-migration size         117,462,947 bytes
Stage 7.1 size             117,462,947 bytes
both SHA-256               c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result                 identical
```

The retained proof workspace is `/tmp/pbrt-sky-stage7.GJcx7S`. The complete
`.venv` suite runs 139 tests (130 passed, nine skips), system Python passes all
124 non-GUI tests, live validation reports zero errors, and pipeline syntax is
clean. No production render was launched. Stage 7.2 migrates the three cloud
formations and copies their actually used shared construction/medium values
into each cloud.

## Stage 7.2 — self-contained sky clouds

Status: implementation and validation complete from pushed sky checkpoint
`33111c6`

All three retained formations moved in stable order from the temporary shared
cloud module into `scene_description.sky.clouds[]`: disabled `left_cumulus`,
disabled `right_cumulus`, and enabled `overcast_cloud_deck`. Each cloud now
owns its name, enabled state, placement, dimensions, resolved density generator
and resolution, shape, noise, depth slope/profile, lobes, and complete medium
optics/underside controls. Shared appearance, shape, and fractal-noise sources
no longer exist. The execution-only C++/Python selection moved separately to
`sky.cloud_grid_builder`.

`configured_cloud_module()` adapts these self-contained entries to the tested
cloud generator and normalized C++ contract without reintroducing live shared
defaults. For every formation—including the two disabled alternatives—the
new configuration produces a normalized contract exactly equal to its
pre-migration contract. Snapshot executable freezing, validation, description,
builder routing, and the Qt cloud selector use the new paths.

```text
cloud order       ['left_cumulus', 'right_cumulus', 'overcast_cloud_deck']
enabled clouds    ['overcast_cloud_deck']
grid builder preserved       True
all normalized jobs equal    True
pre-migration size           117,462,947 bytes
Stage 7.2 size               117,462,947 bytes
both SHA-256                 c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64
cmp result                   identical
```

The retained proof workspace is `/tmp/pbrt-clouds-stage7.NBGFcc`. The complete
`.venv` suite runs 140 tests (131 passed, nine skips); system Python passes all
125 non-GUI tests. Live validation and pipeline syntax are clean. No production
render was launched. Stage 7 is complete; Stage 8 begins atmosphere, including
absorbing the retained `fog_volume` boundary into the fog object.
