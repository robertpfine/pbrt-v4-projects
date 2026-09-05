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

The compiled cloud-grid validation gate is complete. The first four live
migration stages—file names/paths, camera settings, render settings, and the
scene-description shell/context—are also complete and recorded in
`docs/config-migration-progress-2026-09-04.md`. Their bounded structural
rebuilds are byte-identical to the pre-migration PBRT scene. The next
implementation stage migrates landforms and their surface objects one complete
generator at a time.

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

Stage 4 final verification increased the project suite to 102 tests: 93 passed
in `.venv` and nine dependency-aware tests were skipped. System Python passed
all 88 non-GUI tests. The live validator reports zero errors and the exact
migration-only comparison against `9e91e65` reports true. A fresh isolated
build of an in-memory `020525` configuration migrated through Stages 1–4 again
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

## Explicit cloud boundary implementation

The horizon-cloud investigation after configuration migration established that
the sharp vertical split was a finite cloud-volume face, not an unexplained
noise seam. Increasing samples and grid density sharpened the face; changing
the box width symmetrically did not reliably move the projected edge; aligning
the camera and box X axes removed the oblique side-face view. Raising and
extending the deck demonstrated that a finite volume can cover the practical
horizon, while also showing that `depth_slope` is not a true rotated boundary.

The artist authorized a more precise geometry control after confirming these
requirements: four explicit bottom vertices, derived top/thickness,
independent face fades, camera/geometry validation, and a projected-boundary
diagnostic. Implementation deliberately preserved the live manually edited
`scene_workspace/config.json`; no new cloud values or boundary mode were
silently activated.

### Geometry and density work

- Added `cloud_boundary.py` as the renderer-independent geometry model.
- Added the optional `corner_prism` mode with world-space `near_left`,
  `near_right`, `far_right`, and `far_left` bottom points plus a positive
  vertical `thickness`.
- Required a convex, non-crossing XZ footprint and one coplanar bottom. This
  guarantees that the closed triangle boundary and analytic density support
  describe the same solid.
- Derived all eight boundary vertices and the enclosing PBRT grid bounds.
- Kept `axis_aligned` as the absent-field/default mode and retained the exact
  established `depth_slope` path for old configurations.
- Made `corner_prism` and enabled `depth_slope` mutually exclusive.
- Clipped density to the prism in both Python and C++, while retaining an
  axis-aligned PBRT storage grid around it.
- Evaluated vertical density variation and underside optical coefficients
  relative to the local authored bottom plane.
- Anchored plane-following noise at the near-edge midpoint, matching the
  legacy slope's zero-offset face so an equivalent corner conversion preserves
  the existing 3D noise field.
- Extended mottled-veil edge fades from the compatible XYZ triple to optional
  independent `left`, `right`, `bottom`, `top`, `near`, and `far` fractions.
  Explicit zero means no fade at that face.
- Changed the PBRT medium boundary writer to emit the authored prism rather
  than the enclosing grid box.

### Validation and diagnostics

- Extended `SceneConfig` boundary validation and added the same strict geometry
  checks at cloud construction.
- Reject an enabled corner prism containing the camera eye before expensive
  density generation begins.
- Added executable `cloud_boundary_diagnostic.py`. It projects all eight
  boundary vertices through the configured PBRT perspective camera, reports
  pixel/depth/frame status, reports whether the camera is inside, emits JSON on
  request, and can write an SVG wireframe without building or rendering a
  scene.
- Ran the diagnostic against the untouched live `overcast_cloud_deck`. It
  parsed successfully, identified the legacy `axis_aligned` mode, and reported
  the current camera outside the volume. A disposable SVG was written under
  `/tmp`, not into the scene workspace.
- Added `docs/cloud-boundary-controls.md` with the schema, fade semantics,
  validation rules, diagnostic commands, generator behavior, and the finite
  perspective limitation.

### Verification record

- The compiled cloud-grid helper rebuilt successfully after the C++ changes.
- A focused 44-test run passed with five dependency-aware skips.
- New tests cover exact prism bounds and mesh vertices, density exclusion,
  asymmetric near-face fade, twisted-bottom rejection, slope conflict,
  camera containment, PBRT camera projection, SVG output, and tilted/skewed
  RGB-grid parity between Python and C++.
- The first full 132-test run found one snapshot-fixture dependency omission:
  the frozen standalone `cloud_grid_contract.py` now imports the lightweight
  `cloud_boundary.py`, but that synthetic fixture copied only the contract.
  The snapshot source set already captures root Python files in production;
  the fixture and compatibility sidecar list were corrected to make the new
  dependency explicit.
- The corrected full project-virtual-environment suite passed all applicable
  tests: 134 run, 12 dependency-aware skips, zero failures.
- System Python passed all 119 non-GUI tests, including the NumPy/Pillow-backed
  atmosphere and exact authored boundary-mesh checks. Its only full-discovery
  omission is the expected unavailable PySide6 GUI module, which is covered by
  the project virtual environment.
- The C++ source also compiled separately with `-Wall -Wextra -Wpedantic`
  without warnings.
- The authoritative live JSON passed `SceneConfig` validation with zero
  errors. `git diff --check` and Python bytecode compilation passed. No PBRT
  production render was launched.

### Safe live-config conversion after the exploratory studies

Before changing the live JSON, its complete manual exploratory state was
committed and pushed as `6bacde3` (`Checkpoint exploratory cloud deck
settings`). That checkpoint preserves the changed camera, 56 samples, larger
volume and grid, softer/no-detail noise, and -6000 slope without creating a
second live scene configuration.

Inspection of the pre-experiment config stored in `23021f9` found a specific
camera-boundary hazard. Its cloud center/dimensions produce base Y 450 through
1250, but the axis-aligned proxy expands globally to Y 150 when the -300 far
slope is enabled. The camera eye `[290, 165, 365]` is consequently inside the
proxy box even though it is below the actual local sloped density. The baseline
was therefore never restored or run as an intermediate live state.

The safeguards and conversion were completed as follows:

- Extended both `SceneConfig` and the scene builder to reject a camera inside
  any enabled cloud boundary, including legacy axis-aligned volumes, before
  grid generation.
- Added direct tests for both legacy and corner-prism camera containment.
- In one `apply_patch` transaction, restored all checked-in camera, sampling,
  cloud placement/dimensions, grid resolution, noise, and optical values;
  inserted the equivalent prism; and disabled `depth_slope` while retaining
  its inactive -300 value.
- The resulting config differs from the config in `23021f9` in exactly two
  semantic respects: the corner-prism block is present and
  `depth_slope.enabled` changes from true to false.
- The prism spans X -40000 to 10000. Its near edge is Y 450 at Z 3000, its far
  edge is Y 150 at Z -23000, and its vertical thickness is 800.
- `SceneConfig` reports zero live-config errors. The projection diagnostic
  identifies `corner_prism` and reports the camera outside. Its disposable SVG
  is `/tmp/overcast-boundary-baseline-prism.svg`.
- The actual live overcast configuration completed through the compiled grid
  builder in a disposable directory using eight builder threads. It returned
  zero in 0.572 seconds and wrote a 39,936,339-byte PBRT medium declaration,
  which was then removed with the temporary directory. PBRT was not invoked.
- Final verification ran 136 tests in the project environment with 13
  dependency-aware skips and no failures. System Python passed all 121 non-GUI
  tests. `git diff --check` passed. No PBRT render was launched.

## Centered-prism A/B and hybrid shell proof-of-concept decision

The first end-to-end prism run (`210419`) was artist-aborted after the PBRT
completion estimate failed to converge. Direct comparison against successful
archived `075647` found that the 117 MB generated scenes differ only in the
cloud boundary's eight point coordinates; the complete medium grids and all
other PBRT declarations are byte-identical. PBRT source inspection confirmed
that an interface surface switches a vacuum ray into the named medium only on
an entering intersection. The legacy proxy contained the vacuum-initialized
camera, whereas the prism correctly placed it below and outside the volume.

A camera-frustum intersection sample measured 47.66 percent of rays entering
the initial prism, with inside distances of approximately 3,755 units median,
17,794 units at the 95th percentile, and 34,907 units maximum. This established
a plausible cost mechanism but was deliberately tested rather than accepted as
a complete failure diagnosis.

The canonical centered configuration changed camera eye/look X to zero, cloud
placement X to zero, and the boundary X span to -25,000 through 25,000. All
other cloud controls remained fixed. Visible-terminal run `214414` completed
at one sample and `214712` completed at eight samples, both at 2000x1500 and
depth 20. The latter archived config has SHA-256
`45bc26e8d35ac7e8bef85a0e0dd6fa9ff1ffd19db549b4010dcc36d20afb08cd`
and is again byte-identical to the authoritative live config.

The controlled horizon-coverage experiment changed only the two far-bottom Y
coordinates from 150 to -600. Projection moved that edge from about row 708 to
row 759, covering the apparent ground edge after accounting for the 120-unit
bottom fade. Visible-terminal run `215251` then reproduced the operational
death loop: PBRT's total-time estimate increased and no image completed. On the
artist's order, host PID 977081 was terminated. The frozen run was retained and
the live JSON restored exactly to `214712`.

The next authorized engineering direction is a conservative hybrid proof of
concept. Distant horizon clouds will use a hollow thin spherical shell whose
inner and outer radii bound the camera-ray medium distance; existing local
cloud formations will remain available as ordinary finite volumes. The proof
of concept must add schema, geometry, density, transition, camera, and path-risk
validation before rendering, preserve legacy axis-aligned and corner-prism
output, and begin with a low-sample run in the artist-visible terminal.

### First spherical-shell render and depth ordering

The first hybrid-shell implementation uses two concentric PBRT sphere
interfaces around a hollow camera cavity and PBRT's built-in procedural
`cloud` medium between them. Existing finite RGB-grid cloud formations remain
available and unchanged. The new `spherical_shell` boundary validates positive
inner radius and thickness, matching outer dimensions, camera placement inside
the hollow cavity, and the resulting bounded camera-ray path. The associated
`pbrt_cloud` density generator is restricted to this boundary and medium type.

Focused tests, full project tests, bytecode compilation, live-config
validation, and a non-rendering scene build passed. The first visible-terminal
render, `223757`, used a camera-centered shell with inner radius 5,000,
thickness 800, PBRT procedural density 0.65, wispiness 0.8, frequency 4.5, one
sample, and depth 20. It completed and archived successfully. The spherical
geometry eliminated both the rectangular box edge and the clear-sky horizon
gap: every unobstructed camera ray traversed exactly 800 world units of cloud
medium.

The run was nevertheless too expensive for iteration: it required roughly 14
minutes at one sample and remained strongly Monte Carlo noisy. Geometry is
therefore proven, but these rendering/medium settings are not accepted as a
production configuration.

Image inspection also established an independent depth-ordering error. The
shell began 5,000 units from the camera, while the three enabled fractal-tree
placements are approximately 8,600, 9,600, and 10,500 units away, so the cloud
medium necessarily appeared in front of all tree crowns. The vista plane is
50,000 units square and spans both near and distant scene regions. The next
single-variable geometry state moves the inner radius to 12,000 while retaining
the 800-unit thickness and camera-centered shell. This places the tree line in
the clear cavity while allowing a nearer portion of the vista to remain in
front of the shell and its farther portion to appear behind it. No second
render is authorized by this configuration edit alone; performance is to be
isolated before another full-frame run.

The artist authorized a reduced-resolution depth-ordering proof before another
full-resolution attempt. Visible-terminal run `232917` used 500x375, one
sample, and otherwise retained the `223757` camera, shell thickness, procedural
density, optics, and depth-20 integrator. It completed and archived normally in
about 17 seconds end-to-end. The PNG verifies the intended ordering: primary
rays reach all three tree silhouettes before entering the cloud shell, while
the procedural cloud remains visible behind them. Nearer vista surface is in
the clear cavity and farther vista/horizon rays cross the shell. The live film
resolution was restored to 2000x1500 immediately after inspection; the
12,000/12,800 shell radii remain active for the next controlled experiment.

Local PBRT-v4 source inspection identified the relevant procedural-cloud cost
controls. Every sampled candidate medium event evaluates a fixed five-octave
noise sum. Any positive `wispiness` adds two derivative-noise domain-warp
evaluations. `frequency` changes feature scale but does not change those loop
counts. Procedural `density` changes the returned point density, but PBRT's
`CloudMedium` constructs a homogeneous majorant from `sigma_a + sigma_s`
without multiplying by that procedural density, so reducing `density` alone
does not proportionally reduce candidate-event work. The controlled levers
that can materially reduce integration cost are zero wispiness, smaller
scattering/absorption coefficients, and lower volumetric path depth. These
must be tested independently at reduced resolution before increasing samples.

### Full-resolution shell result and Blender architecture research

At the artist's request for one image suitable for evaluation, render `014103`
used 2000x1500, eight samples, depth 6, shell radii 12,000/12,800, density 0.65,
frequency 4.5, zero wispiness, scattering
`[0.00085, 0.00092, 0.001]`, and absorption
`[0.00015, 0.00016, 0.00018]`. Snapshot creation began at 01:41:03 and the
final PNG archived at 01:41:33, so the full pipeline completed in about 30
seconds. The live and archived configs are byte-identical at SHA-256
`5e2733c7c95b0f914e506cbeaf7ad3c256d3d4325be319b381bffcc82ee6b739`.

The image has correct depth ordering and no box edge, but the artist rejects
the dome-medium direction on visual grounds. It produces a large radial
opening/halo, flat cloud structure, and residual stippling rather than a
convincing overcast deck. Do not treat its speed or geometric correctness as
artistic acceptance.

Research against official Blender documentation establishes that Blender does
not generally solve this distant-sky problem with a camera-centered procedural
participating-medium shell. Its World surface is an infinitely distant
directional background and can use an environment texture. True clouds are
instead represented as bounded closed-mesh volumes or Volume objects, commonly
using sparse OpenVDB data that Cycles converts to NanoVDB and samples with a
bounding mesh. Blender explicitly warns that world volumes fill all space and
recommends a surrounding volume object for atmospheric scattering. Cycles
limits noisy multiple volume scattering in practice, supports adaptive
sampling and denoising, and retains a biased ray-marching option with step-size
and maximum-step safeguards. EEVEE uses a view-frustum 3D texture with an
explicit depth range, and Blender Studio also documents production compositing
of a fast EEVEE volume pass over a Cycles surface render.

The directly applicable PBRT architecture is therefore a deterministic
environment/background cloud image for the distant overcast and horizon, plus
separate bounded RGB-grid or NanoVDB volumes only where local 3D interaction is
artistically valuable. A background environment has no rectangular boundary,
is always behind scene geometry, and cannot create a long cloud-medium path.
This is the recommended replacement for the rejected volumetric shell.
