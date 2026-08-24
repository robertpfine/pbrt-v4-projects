# Project Continuity

Last updated: 2026-08-24

## Purpose

This repository is evolving into a modular procedural-art system for PBRT-v4.
Its goal is not strict photorealism. The goal is to generate visually compelling
tree- and plant-like objects, place them in procedural landscapes, and shape the
result through atmosphere, light, camera, and post-render compositing.

The user prefers decisive, informative bookend experiments over sequences of
barely perceptible parameter changes. Artistic evaluation is made from the
locally archived renders, normally while a visible terminal displays generation
and PBRT progress.

## Repository and checkpoint

- Repository root: `/home/rpf4/my-pbrt-projects`
- Active branch: `space-colonization`
- Remote: `https://github.com/robertpfine/pbrt-v4-projects.git`
- Last pushed visual-system checkpoint before this document: `317c891`
  (`Add composited light shafts and foreground terrain leveling`)
- Primary working scene: `rgbgrid-medium/config.json`
- Renderer: PBRT-v4 with CUDA/GPU rendering
- Normal pipeline entry point: `./render_pipeline.sh rgbgrid-medium`
- Shaft-composite entry point: `python3 render_shaft_composite.py rgbgrid-medium`

## Procedural object systems

- `space_col.py`: three-dimensional space-colonization trees, continuous
  attraction points, tropism, trunk and branch-radius work, decimation and
  render hierarchy controls, and foliage support.
- `lsystem.py`: L-system tree experiments, including evergreen and live-oak
  architectural studies.
- `fractal_tree.py`: separate recursive/fractal tree system. Its crownlet
  controls produced the strongest recent tree-like object and should remain a
  modular alternative to L-systems and space colonization.
- `phyllotaxis.py`: planar phyllotaxis and sunflower construction based on the
  Figure 4.1 study from *The Algorithmic Beauty of Plants*.
- `terrain.py`: deterministic rolling-hillside terrain with fBm-style value
  noise, slope, terrain-aware root placement, and a smooth camera-facing
  transition toward a level foreground.

The long-term architecture should permit these systems to be used separately
or together. In particular, structural scaffolds may come from fractal or
L-system rules while fine branching or crown occupation may come from space
colonization.

## Current scene state

The active scene contains a fractal tree on a large rolling hillside with
Perlin-like heterogeneous morning fog and parallel sunlight shafts. The terrain
has been expanded to fill the frame and now transitions from a strong hillside
around the tree toward a genuinely horizontal foreground while retaining its
rolling noise.

The base and shaft sunlight directions are synchronized so the visible shafts
agree with the tree shadow. A distant light passes through a procedural
cloud-breakup aperture. The shaft pattern is currently strong and attractive,
although exact aperture placement remains an artistic tuning point.

Important recent local render:

- `Archive/rgbgrid-medium_20260824_000304_composite.png`

The user described this scene as very beautiful and judged that its terrain,
fog, tree, parallel shafts, and light were working in concert. The brightest
aperture pattern moved in the desired leftward direction, but its exact shape is
slightly unusual. Preserve this state before further tuning.

Current relevant configuration values include:

- `shaft_sun.scale`: `12.0`
- `sun_aperture.beam_target`: `[-70.0, 60.0, 130.0]`
- terrain size: `[1200.0, 1200.0]`
- terrain resolution: `[257, 257]`
- hillside grade: `0.40`
- foreground leveling: start `0`, end `180`, minimum grade ratio `0`, target
  height `0`
- composite base opacity: `0.30`
- composite shaft opacity: `0.85`
- shaft-pass tree reflectance scale: `0.20`
- shaft-pass terrain reflectance scale: `0.05`

## Shaft compositing

`render_shaft_composite.py` renders two PBRT images and combines them in linear
RGB:

1. `_base.png`: tree, terrain, fog, ambient illumination, and unmasked sun.
2. `_shaft.png`: isolated aperture-filtered parallel sunlight interacting with
   the atmosphere.
3. `_composite.png`: final artwork produced from the two passes.

Each composite render must archive the traditional five reproducibility file
types—PNG, PBRT, JSON, Python, and shell script—plus the composite-specific
script, documentation, and both diagnostic passes. Existing composite bundles
through `000304` were backfilled with their timestamped `render_pipeline.sh`.

## Render archive policy

The user reads completed images directly from:

`/home/rpf4/my-pbrt-projects/Archive`

For an ordinary render, retain:

- final PNG
- PBRT scene
- exact `config.json`
- exact `build_scene.py`
- exact `render_pipeline.sh`

For a shaft-composite render, additionally retain:

- base and shaft PNGs
- base and shaft PBRT scenes
- `render_shaft_composite.py`
- shaft-compositing documentation

The intermediate images are technically required to explain and diagnose the
composite even though the user normally evaluates only `_composite.png`.

## Documentation policy

Documentation should evolve alongside functionality. Current focused documents
include:

- `docs/fractal-tree-configuration.md`
- `docs/terrain-configuration.md`
- `docs/atmosphere-configuration.md`
- `docs/lighting-configuration.md`
- `docs/shaft-compositing.md`

Research PDFs are local reference material and should not be pushed to GitHub.

## Working preferences and safeguards

- Show render progress in a visible terminal.
- Use the CUDA device; render duration is not presently onerous.
- Prefer strong comparison tests when a visual parameter is uncertain.
- Do not produce undocumented collections of near-identical renders.
- Identify renders by their archive timestamp.
- Inspect the local archived image rather than waiting for Google Drive.
- Do not alter a successful visual state without first creating a checkpoint.
- Keep generated PBRT scenes, archives, backups, research PDFs, raw session
  logs, and verbatim transcripts out of Git.
- Commit and push meaningful code/configuration/documentation checkpoints to
  the `space-colonization` branch.

## Immediate follow-up work

1. Decide whether to retain `000304` exactly or revisit the cloud-aperture
   placement later. Do not resume tiny positional tweaks without a clear visual
   comparison strategy.
2. Continue broadening the modular scene system: procedural terrain types,
   skies/clouds, atmosphere, lighting controls, and reusable plant/tree
   components.
3. Eventually reorganize the organically grown `config.json`, but only after
   the current functional modules stabilize.
4. Preserve readable and raw conversation archives in the gitignored
   `SessionArchive/` directory.

## Conversation preservation

The source Codex event log for the multi-day session is stored outside the
repository under the user's `.codex/sessions` directory. A compressed immutable
snapshot and a readable visible-message transcript are stored in
`SessionArchive/`. The raw snapshot is authoritative and includes embedded
images and tool records. The Markdown transcript preserves the visible textual
conversation in chronological order and marks image positions.
