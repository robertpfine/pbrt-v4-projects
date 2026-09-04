# C++ Cloud-Grid Validation Log — 2026-09-04

Status: validation complete

## Purpose

Validate the compiled C++ cloud-grid generator through the existing legacy
configuration and render infrastructure before beginning the approved
`scene_workspace/config.json` migration. Preserve enough detail to distinguish
grid-generation defects from PBRT volumetric-render cost, scene-expansion cost,
or pipeline integration defects.

## Safeguards

- Active branch at investigation start: `pbrt-v4-art-studio`.
- Starting checkpoint: `62c8320` (`Add immutable render snapshots and compiled
  cloud grids`), synchronized with `origin/pbrt-v4-art-studio`.
- Starting worktree was clean.
- `scene_workspace/config.json` remains the sole authoritative live scene
  configuration.
- The retained failed-run workspace
  `scene_workspace/.render_runs/20260904_011516` will not be deleted or altered
  during diagnosis.
- No new render will start until a bounded Python-versus-C++ comparison has
  been specified and checked.
- No live schema migration will begin until the cloud-grid validation is
  resolved and checkpointed.

## Investigation record

### 2026-09-04 — recovery and source review

- Read the canonical `docs/continuity.md` completely.
- Read the routed artistic vision, Qt proof-of-concept, scene-module boundary,
  approved fourteen-issue schema, ground-level schema, detailed engineering
  progress, and atmosphere-configuration documents.
- Verified the active branch and clean worktree before this log was added.
- Verified that no PBRT, scene-builder, render-pipeline, shaft-composite, or
  cloud-grid-builder process remained active.
- Located the compiled implementation at `cpp/cloud_grid_builder.cpp`, its
  normalized Python adapter at `cloud_grid_contract.py`, its build script, and
  its automated parity tests.

### 2026-09-04 — retained run `20260904_011516`

Initial artifact facts:

- The immutable input manifest exists and identifies the exact frozen source
  configuration and participating source hashes.
- The run used the C++ backend with automatic threading and Python fallback
  enabled.
- The C++ grid job completed before PBRT rendering. Its normalized job JSON is
  1,855 bytes and its generated PBRT medium declaration is 39,936,339 bytes.
- The full frozen scene build also completed. `scene.pbrt` is 1,044,724,173
  bytes and was completed at 01:18:42 EDT, about 3 minutes 25 seconds after the
  01:15:16 snapshot timestamp.
- No final PNG, EXR, or captured render log exists inside the retained run
  workspace. The visible terminal output was not redirected to a file.
- Effective render controls were `2000 x 1450`, Halton 512 samples per pixel,
  `volpath` maximum depth 80, GPU enabled, and statistics enabled. The killed
  run was therefore not the accepted 8000 x 5800 master resolution, but it was
  still a high-cost 2.9-million-pixel volumetric render.
- Fog was disabled. One `mottled_veil` overcast deck was enabled at center
  `[-15000, 850, -10000]`, size `[50000, 800, 26000]`, and grid resolution
  `[160, 40, 120]`, with a far-depth Y offset of `-300`.
- The unrelated scene-expansion burden remained large: 3,400,000 grass tufts
  and 3,500 poppies were enabled.

Interpretation at this point: grid creation and the full Python scene build
both terminated successfully. The observed non-progress occurred after the
1.044 GB PBRT scene had been produced, during PBRT ingestion/preparation or GPU
volumetric rendering. This narrows the failure location but does not yet prove
whether the C++-generated medium, the cloud configuration, PBRT volume
traversal, or the overall workload caused it.

### 2026-09-04 — exact retained-grid parity and boundary review

- Recomputed the complete current overcast optical grids with the Python
  `CloudFormation` reference and compared them directly with the retained C++
  PBRT declaration.
- Absorption comparison: 2,304,000 C++ values and 2,304,000 Python values;
  maximum pre-serialization difference `5.0e-6`, mean difference approximately
  `1.169e-6`, and zero differences after both sides were formatted to the
  builder's five-decimal PBRT precision.
- Scattering comparison: 2,304,000 C++ values and 2,304,000 Python values;
  maximum pre-serialization difference `5.0e-6`, mean difference approximately
  `1.012e-6`, and zero differences after five-decimal formatting.
- The retained C++ declaration hash is
  `686cd006a77d4843d1363245d82d51c5440ece5304373bf7cf87416e6c220426`.
- The normalized job, Python reference, C++ declaration, and boundary geometry
  agree on expanded medium bounds `[-40000, 150, -23000]` through
  `[10000, 1250, 3000]`. The base deck bounds are
  `[-40000, 450, -23000]` through `[10000, 1250, 3000]`; the enabled far-depth
  slope expands the lower Y bound by 300.
- The camera at `[290, 165, 365]` lies outside but only 15 world units below the
  expanded axis-aligned cloud boundary. The builder correctly does not start
  the camera inside the cloud medium. The boundary transitions from the named
  cloud medium on its interior to vacuum on its exterior.
- The exact PBRT invocation reconstructed from the frozen config and pipeline
  is the configured PBRT-v4 executable with `--gpu --stats`, an archive PNG
  output path, and the frozen `scene.pbrt` input. No output image with the
  failed run's timestamp exists, confirming that PBRT did not complete.

The C++ and Python paths therefore supply PBRT with the same grid values at the
actual serialization precision. A visual A/B remains useful for end-to-end
pipeline validation, but a difference in render completion is no longer
expected from density or optical values alone.

### 2026-09-04 — bounded A/B design

The control and experimental renders will use the existing legacy schema and
the same current overcast formation. To remove costs unrelated to cloud-grid
integration, both will use `640 x 464`, 8 pixel samples, `volpath` depth 20,
disabled grass, disabled poppies, and disabled remote synchronization. The
camera, terrain, vista, sky, sun, cloud placement, cloud dimensions, full
`160 x 40 x 120` grid resolution, density field, and optical values remain
unchanged. The Python control runs first; the C++ run changes only
`scene.sky.clouds.grid_builder.backend`.

These temporary diagnostic changes are made in the sole authoritative live
configuration. The exact pre-test state is already recoverable from checkpoint
`62c8320` and will be restored after both snapshots have frozen their inputs.

Pre-render verification:

- Confirmed JSON syntax and queried every intended diagnostic value directly.
- Confirmed the overcast formation, underside optics, terrain, camera, sky, and
  sun remain enabled and unchanged.
- Confirmed remote synchronization, grass, and poppies are disabled; film is
  `640 x 464`, sampling is 8, depth is 20, and the first backend is `python`.
- Ran 21 focused cloud, compiled-grid, and configuration-model tests in the
  repository Qt virtual environment; all 21 passed.

### 2026-09-04 — Python control render `020525`

- The legacy snapshot/build/render/archive pipeline completed successfully with
  `grid_builder.backend: "python"`.
- Output image:
  `Archive/Poppy_Field_Overcast_8AM_Study_20260904_020525.png`.
- The archived PBRT scene is 117,462,947 bytes, versus 1,044,724,173 bytes for
  the killed full-population run. This confirms that disabling grass and
  poppies removed most unrelated scene-expansion cost while retaining the full
  cloud medium.
- The PNG is 640 x 464 and visually contains the expected meadow/vista beneath
  a continuous gray overcast field. At only 8 samples it is intentionally
  noisy; this is a completion and equivalence diagnostic, not an artistic
  candidate.
- Artifact hashes recomputed from disk match the archive manifest: PNG
  `5a10bb2b2d0afbb0f36fe96935181e18ae03ab253923baa834bb40a71d9a0dc5`,
  PBRT `c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64`,
  and config
  `ebfe4189c20308f6779054d318ae38a3e96f24db77438cc6dd977df736095770`.
- No PBRT or pipeline process remained after completion.

Process-monitoring note: a sandboxed process query did not expose the host
GNOME-terminal process. While the visible pipeline was finishing, the frozen
builder was briefly invoked a second time to recover what appeared to be a
builder failure. The archived artifacts had already been finalized from the
pipeline and their hashes match their manifest; the duplicate deterministic
build affected only the retained temporary run workspace, not the archived
control bundle. Subsequent active-process checks use host-level inspection.

Archive observation after both runs: the Python control has no normalized C++
job because that backend does not create one. The C++ bundle correctly retains
`cloud_job_cloud_0_overcast_cloud_deck.json`; its generated standalone PBRT
medium is incorporated into the archived complete PBRT scene. This behavior is
consistent with the implemented archive contract and is not a newly identified
reproducibility defect.

### 2026-09-04 — C++ comparison render `020829`

- Changed only `scene.sky.clouds.grid_builder.backend` from `python` to `cpp`.
  All other diagnostic and artistic values matched the Python control.
- The complete legacy snapshot/build/render/archive pipeline succeeded. The
  compiled `160 x 40 x 120` grid was generated, included in the complete scene,
  accepted by PBRT-v4's GPU path, and rendered without a stall.
- Output image:
  `Archive/Poppy_Field_Overcast_8AM_Study_20260904_020829.png`.
- The C++ and Python PNGs are byte-for-byte identical. Both have SHA-256
  `5a10bb2b2d0afbb0f36fe96935181e18ae03ab253923baa834bb40a71d9a0dc5`.
- The C++ PBRT scene is 117,462,944 bytes and the Python scene is 117,462,947
  bytes. After normalizing the harmless medium comment and accounting for C++
  integer-style versus Python float-style bound literals, the only observed
  structural differences are those text representations; they denote the same
  numeric bounds. Grid arrays are identical at serialized precision as already
  established above.
- The archived normalized C++ job hash is
  `06f68833113896d062c7cfa2ded7a5fc95c87122e073b1d894ff84ecd680d321`.
- The C++ archive manifest contains and hashes the normalized job, executable,
  native Perlin library, source, config, complete PBRT scene, and image.

Validation conclusion: the C++ cloud-grid implementation is equivalent to the
Python reference for the complete current overcast job and is valid end to end
through immutable snapshotting, legacy scene construction, PBRT-v4 GPU
volumetric rendering, and local archival. The earlier killed run is not evidence
of a C++ grid-value or integration divergence. Its completed grid/build phase,
large expanded scene, 512 samples, depth 80, and full vegetation burden remain
the supported explanation for impractical behavior, although the absent
captured terminal log prevents reconstructing PBRT's exact last internal phase.

## Completion record

- All five planned validation steps were completed.
- Restored `scene_workspace/config.json` exactly to its pre-test committed
  contents. Its Git blob is again
  `d602607f884eb79b9766c8738118b7a555df2434`, matching checkpoint `62c8320`,
  and its SHA-256 is
  `916c78e193304476a893992474a179d55c7fc743bbdf780cf579b952fe8a58b3`.
- The Qt virtual environment completed all 72 discovered tests: 66 passed and
  6 dependency-aware tests were skipped.
- Production system Python completed all 64 non-GUI tests with no failures,
  including the NumPy/Pillow-dependent atmosphere and texture tests.
- `git diff --check` passes.
- No source-code or permanent artistic-configuration change was required. This
  validation log and the continuity/progress updates are the only intended
  tracked changes in the checkpoint.

The pre-migration cloud-grid gate is satisfied. The first live migration stage
was subsequently completed and is recorded in
`docs/config-migration-progress-2026-09-04.md`.
