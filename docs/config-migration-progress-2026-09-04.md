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
