# Engineering progress log — 2026-09-04

This is the detailed implementation log for the pre-migration configuration,
render-snapshot, and compiled cloud-grid work. The canonical concise handoff
remains `docs/continuity.md`; this document preserves engineering detail that
would make that handoff unwieldy.

## Scope and safeguards

- Active branch verified: `pbrt-v4-art-studio`.
- `docs/continuity.md` was read completely before implementation.
- `scene_workspace/config.json` remains the one authoritative live scene file.
- No production PBRT render was started during this work.
- The accepted `093054` image and its archived configuration were not altered.
- The live configuration remains the unaccepted overcast work in progress.
- The ground-level schema is documentation only; it is not a second runnable
  configuration.

## Configuration-schema work

- Completed the reviewed architectural draft in
  `docs/config-schema-new-scene.md`, including all fourteen resolved issues.
- Added `docs/config-schema-new-scene-ground-level.md` as the engineering
  translation: exact fields, types, validation, ownership, current-to-proposed
  path mapping, generator consumers, migration order, and normalized C++ cloud
  contract.
- Preserved the artist-approved ordering and concepts: file names, file paths,
  camera settings, render settings, then scene description; landform-first
  scene construction; clouds under sky; fog/haze/mist/rain under atmosphere;
  flora and trees as landform surface objects; independent surreal or placed
  objects under `scene_description.objects`.
- The artist is not expected to conduct a leaf-by-leaf deep technical review.
  Future escalation is limited to visible terminology, artistic-control
  placement, and scene-building workflow choices.

## Mandatory immutable render snapshots

Implemented `render_snapshot.py` and connected it to both render paths.

### Snapshot transaction

1. One timestamp is created at render launch.
2. The live JSON is copied first into
   `scene_workspace/.render_runs/<timestamp>/repository`.
3. The copied JSON is parsed and validated; all subsequent build reads use it.
4. Participating Python, shell, C++, documentation, configured compiled helper,
   and required native noise inputs are copied into the frozen repository.
5. Frozen inputs are made read-only and recorded with SHA-256 hashes in
   `input_manifest.json`.
6. Scene construction and rendering execute inside the frozen repository.
7. The local Archive is finalized first with the exact config, generated PBRT,
   normalized cloud jobs, relevant scripts, source tarball, and hash manifest.
8. Optional Google Drive copying selects every file sharing the render prefix.
9. The temporary workspace is removed only after successful local finalization;
   failed runs retain it for diagnosis.

### Pipeline changes

- `render_pipeline.sh` now freezes inputs before reading render values or
  invoking a builder.
- It runs `build_scene.py`, procedural generation, and PBRT against frozen paths.
- It no longer archives whatever live JSON or source happens to exist after a
  long render.
- It no longer modifies the archived PBRT with `sed`; the archived scene is the
  exact scene given to PBRT.
- `render_shaft_composite.py` re-executes its frozen copy and builds both passes
  from the same immutable inputs.
- Composite remote-sync failure is non-destructive: the complete local archive
  remains available.
- The active Stage 1 schema rejects directory components in
  `file_names.pbrt_scene` and rejects a `file_paths.scene_files` path that is
  absolute or escapes the frozen repository with `..`.
- Compiled helper paths are constrained to the repository. Missing compiled
  executables are permitted only when the explicit Python fallback remains on.

### Snapshot verification completed

- Live JSON and builder changes made after the freeze marker do not affect the
  active render or its archived configuration.
- Frozen config, sources, PBRT, image, source tarball, normalized cloud jobs,
  and final manifest hashes are exercised by automated tests.
- Cleanup refuses unrelated directories.
- The shaft-composite entry point is verified to re-execute the frozen script
  and frozen configuration.

## Targeted C++ CPU cloud-grid builder

Added:

- `cpp/cloud_grid_builder.cpp`
- `cloud_grid_contract.py`
- `build_cloud_grid_builder.sh`
- `cpp/README.md`
- `tests/test_cloud_grid_builder.py`

### Architecture

- Python remains the scene/configuration owner.
- Python resolves legacy shared/local cloud values into one explicit,
  self-contained contract-version-1 JSON job per enabled cloud.
- C++ does not read the large Art Studio config and therefore is insulated from
  the coming JSON migration.
- The helper supports both existing forms: `lobed` and `mottled_veil`.
- It implements current domain warp, fractional-octave fractal sums, envelope,
  edge fades, depth slope, depth profile, density modulation, dark underside,
  and optical coefficients.
- It emits either `uniformgrid` or `rgbgrid` PBRT medium declarations.
- It writes the PBRT array directly to its output stream and parallelizes voxel
  computation across CPU cores. `threads: 0` uses available cores; explicit
  values are restricted to 1–256 to prevent accidental thread explosions.
- The helper calls the native `noise._perlin` implementation already used by
  the Python reference. No Python code runs inside the voxel loop. This choice
  preserves the established noise field rather than silently replacing its
  visual character with another Perlin implementation.
- The native Perlin shared object is frozen with each compiled render so
  a package change during a long run cannot change the active density field.
- The existing Python grid path remains available through `backend: "python"`
  and as an explicit fallback if the compiled helper cannot run.

### Live technical switch

Only a non-artistic technical block was added beside the existing cloud module:

```json
"grid_builder": {
  "backend": "cpp",
  "executable": "build/cloud_grid_builder/cloud_grid_builder",
  "threads": 0,
  "fallback_to_python": true
}
```

No cloud placement, density, color, noise, resolution, slope, or other artistic
value was moved or changed.

### Parity and deterministic behavior

Automated tests compare serialized C++ output with the existing Python
reference at the established five-decimal PBRT precision:

- lobed density with multiple lobes, domain warp, and fractional octaves;
- mottled-veil RGB absorption and scattering grids;
- depth slope and depth-profile falloff;
- dark underside optical changes;
- identical output with one and four C++ threads.

Maximum accepted numeric difference is `1.1e-5`, corresponding to the existing
five-decimal serialization. All parity tests pass.

### Measurements on the current overcast configuration

- Resolution: `160 × 40 × 120`.
- Voxels: `768,000`.
- C++ automatic multi-core build including subprocess and PBRT file writing:
  approximately `0.55–0.58 seconds`.
- Python reference optical-grid calculation before PBRT text formatting:
  `5.77 seconds`.
- This is at least a roughly tenfold improvement for the cloud-grid phase; the
  comparison is conservative because the Python measurement excluded text
  formatting.

### Full frozen scene-build finding

A complete build was run only inside a disposable frozen snapshot, without
starting PBRT:

- Completed successfully in `208.70 seconds`.
- Peak reported resident memory: approximately `4.60 GB`.
- Generated `scene.pbrt`: `1,044,724,173 bytes` (roughly `1.04 GB`).
- The cloud-grid substep took only `0.58 seconds` within that build.

This cleanly separates two costs. The C++ helper fixes the cloud density-build
bottleneck, but the current expanded vegetation/scene representation now
dominates full scene construction and PBRT file size. It also explains why a
future render may spend significant time reading/preparing the scene even when
the cloud grid itself is fast. No vegetation count or artistic parameter was
changed in response.

The generated compiled medium was also embedded in a minimal PBRT scene and
accepted by PBRT-v4's non-rendering `--format` parser.

## Test record

- Shell syntax checks pass for the standard pipeline, GNOME terminal launcher,
  and C++ build script.
- Python byte-compilation passes for snapshot, composite, cloud adapter, scene
  builder, and new tests.
- C++ builds cleanly with C++17, optimization, pthreads, `-Wall`, `-Wextra`, and
  `-Wpedantic`.
- The project virtual environment ran 72 tests: 66 passed and 6 were skipped
  because that interpreter lacks NumPy/Pillow atmosphere dependencies.
- System Python ran all 64 non-GUI tests, including NumPy/Pillow and composite
  snapshot coverage, with no failures. PySide6 is absent from that interpreter;
  the GUI tests pass in the project virtual environment.
- `git diff --check` passes.

## Temporary artifacts and process state

- Two large disposable frozen build directories created during testing were
  removed after their contents and purpose were verified. One was an incomplete
  snapshot lacking a manifest because the first test wrapper was interrupted;
  it contained only a generated approximately 1 GB PBRT file and was not an
  artistic archive or user-authored input.
- At 2026-09-04 00:58 EDT, no PBRT render, scene builder, cloud-grid builder,
  standard pipeline, or shaft-composite process was running.

## Pre-migration gate completion

The limited visual comparison was completed with the artist's explicit
authorization and is recorded in
`docs/cpp-cloud-grid-validation-2026-09-04.md`. The full current overcast grid
was retained while unrelated grass and poppy expansion and production render
cost were temporarily removed. The Python control `020525` and C++ comparison
`020829` both completed through the immutable legacy pipeline and produced
byte-for-byte identical PNGs. The live configuration was then restored exactly
to its committed pre-test contents.

The compiled cloud-grid validation gate is complete. The first three live
migration stages—file names/paths, camera settings, and render settings—are also
complete and recorded in `docs/config-migration-progress-2026-09-04.md`. Their
bounded structural rebuilds are byte-identical to the pre-migration PBRT scene.
The next implementation stage establishes the `scene_description` shell, name,
and scene context.

Stage 1 final verification ran 86 tests in the project virtual environment:
79 passed and seven dependency-aware tests were skipped. The explicit
system-Python non-GUI suite passed all 75 tests, including NumPy/Pillow-backed
composite and atmosphere coverage. The live JSON validator reports no errors,
the exact migration-only comparison against `1346745` reports true, and the
retained bounded PBRT artifact is 117,462,947 bytes with SHA-256
`c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64`.

Stage 2 final verification increased the project suite to 90 tests: 83 passed
in `.venv` and seven dependency-aware tests were skipped. System Python passed
all 78 non-GUI tests. Its fresh isolated build of an in-memory migrated
`020525` configuration again matched the archived pre-migration PBRT file byte
for byte at the same size and SHA-256. No production render was launched.

Stage 3 final verification increased the project suite to 98 tests: 89 passed
in `.venv` and nine dependency-aware tests were skipped. System Python passed
all 85 non-GUI tests. The live validator reports zero errors and the exact
migration-only comparison against `184eb02` reports true. A fresh isolated
build of an in-memory `020525` configuration migrated through Stages 1–3 again
matched the archived pre-migration PBRT file byte for byte at 117,462,947 bytes
and SHA-256
`c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64`. No
production render was launched.

The native-Perlin snapshot boundary has now been verified directly: when the
frozen adapter is executed from its snapshot repository, it resolves
`render_dependencies/cloud_perlin.so`, not the live installed package.

## Checkpoint status

The implementation is recorded by the Git checkpoint containing this log on
`pbrt-v4-art-studio`. As always, the continuity checkpoint is complete only
after that commit is pushed and `docs/continuity.md` is copied to the required
Google Drive handoff path.
