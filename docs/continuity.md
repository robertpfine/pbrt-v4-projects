# PBRT-v4 Art Studio Continuity

Last updated: 2026-08-30

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
- Current visual-system checkpoints:
  - `573f8b8` (`Add configurable pasture terrain and grass tropism`)
  - `4fa4e9c` (`Add spatial grass tropism and cloud shaft controls`)
  - `95d8b44` (`Add PBRT-v4 Art Studio proof of concept`)
- Primary working scene: `scene_workspace/config.json`
- Renderer: PBRT-v4 with CUDA/GPU rendering
- Normal pipeline entry point: `./render_pipeline.sh`
- Shaft-composite entry point: `python3 render_shaft_composite.py`

## 2026-08-29 PBRT-v4 Art Studio checkpoint

The artist selected **PBRT-v4 Art Studio** as the application name. The term
`Project` remains reserved for the surrounding VS Code workspace and is not an
entity in the artistic hierarchy. The former `rgbgrid-medium` working-directory
name was an obsolete reference to an early volumetric experiment and has been
replaced by the role-based `scene_workspace` name.

`rgbgrid` must never serve as a generic label for atmosphere or volumetrics. It
is retained only where code or historical files refer specifically to PBRT-v4's
RGB-grid medium implementation. The artistic category exposed by the interface
is `Atmosphere`; particular PBRT medium implementations remain subordinate
technical choices.

The active configuration no longer contains a top-level `project` object:

- `scene.name` identifies the current working scene for archive filenames.
- `archive.remote_path` identifies the Google Drive render destination.
- `render_pipeline.sh` accepts an optional config path and defaults to
  `scene_workspace/config.json`.
- The ordinary render command is now `./render_pipeline.sh`.

This naming migration does not change the PBRT-v4/CUDA build. The configured
binary remains `/home/rpf4/pbrt-v4/build/pbrt`, GPU rendering remains enabled,
and no render was launched during the interface implementation.

The initial Qt shell is implemented in `pbrt_v4_art_studio.py`. It provides:

- the approved scene-category hierarchy;
- a central viewer for the latest completed render;
- exact-value controls for established landform, ground, grass, poppy, tree,
  sky, atmosphere, lighting, camera, and render parameters;
- explicit placeholders for the required cloud and distant-hill systems;
- validation, safe saving, JSON reload, render/stop controls, and a persistent
  docked render log;
- no `ADD` catalogue, templates, or real-time image manipulation.

`scene_config.py` mediates the single authoritative JSON file. It validates
known relationships, replaces only explicitly edited JSON value spans so manual
formatting is preserved, saves atomically, and refuses to overwrite a file that
was edited externally after loading.

PySide6 6.10.1 is installed only in the gitignored repository-local `.venv`.
`run_art_studio.sh` starts the interface. The complete 22-test suite passes,
including configuration, placement, pipeline-output, and offscreen Qt tests.
The offscreen implementation screenshot is
`docs/assets/pbrt-v4-art-studio-initial.png`; it is a local generated image and
is retained as documentation rather than treated as render output.

Further interaction corrections followed the first desktop launch. The application
restores the operating-system SIGINT behavior so `Ctrl+C` reliably exits and
returns the terminal prompt. PBRT timed progress snapshots are retained as
ordinary lines in the persistent render log. An attempted single live-line
display placed progress in a visually confusing detached bar and was removed;
the small amount of log output has no meaningful rendering cost.
The viewer now loads the completed local PNG immediately while archive and
Google Drive synchronization continue in the background; it no longer waits
for a very large generated PBRT scene file to finish uploading.

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
- `terrain.py`: deterministic rolling-hillside terrain with explicit bounds,
  fBm-style value noise, partial foreground grading, terrain-aware placement,
  and a broad right-side dip/rise landform that forms the current gully.
- `terrain_surface_texture.py`: deterministic seamless ground maps used below
  the instanced blade geometry.
- `terrain_details.py`: deterministic terrain scatter plus the spatial direction
  field used by grass tropism.

The long-term architecture should permit these systems to be used separately
or together. In particular, structural scaffolds may come from fractal or
L-system rules while fine branching or crown occupation may come from space
colonization.

## 2026-08-28 terrain and poppy checkpoint

The single authoritative scene configuration remains
`scene_workspace/config.json`; do not create per-landform JSON files. Terrain now
selects one named entry with `scene.terrain.active_landform`. The named
`right_dip_rise` and `flat_landform` profiles contain landform geometry only,
while the material, surface treatment, and five instanced detail layers remain
shared siblings under `scene.terrain`. The active profile is currently
`flat_landform`.

The poppy detail layer now contains a reusable botanical plant with a bowed
hairy stem, tropic side buds and foliage, seven color variants, thin textured
transmissive petals, basal blotches, a spheroidal ovary, cylindrical stigma
arms, and a dense ring of cylindrical filaments with vertical anthers. The
isolated `poppy_preview.py`, `pistil_preview.py`, and
`reproductive_preview.py` builders preserve diagnostic views of this work.

Terrain-detail scattering now optionally understands the active camera. The
first poppy `camera_frustum` implementation used a 2% frame margin and a
conservative whole-plant bounding sphere. Render `212758` exposed the resulting
inset trapezoid: poppies stopped inside visible grass borders on the left,
right, and bottom. That rule has now been removed. With
`camera_frustum.enabled` true, `count: 2600` means exactly 2,600 instantiated
poppies whose selected placement references project inside the full camera
frame. There is no percentage inset and edge cropping does not disqualify an
instance. `camera_frustum.placement_reference` explicitly switches between
`flower` and `root`. The active `flower` choice frames the primary blossom and
allows roots below the lower edge, eliminating the systematic grass band caused
by root-based framing. This constraint does not perform terrain-occlusion
testing.

The older render `022442` contained 2,600 updated poppy instances scattered
across the whole terrain rectangle, but only 793 instance origins fell inside
the camera frustum. Render `212758` was the first test of camera-constrained
scatter and motivated the full-frame correction. Render `050817` verified that
all 2,600 poppies populate the visible terrain, but exposed a flower-free band
at the bottom because roots rather than blossoms were being frame-tested. The
new `flower` placement reference corrects that cause. Render `053110` is the
artist-accepted flower-placement baseline: all 2,600 requested instances use
their primary blossom as the full-frame reference, roots may fall below the
lower edge, and natural plant cropping remains allowed.

The current active configuration uses the square camera at eye
`[310, 165, 390]`, looking at `[5, 100, -5]`, with a 55-degree field of view.
Grass is enabled as 3.4 million seven-blade tufts with blade height `[8, 45]`.
Poppies are enabled at 2,600 instances with randomized scale `[16, 47]`. Both
L-system tree entries and both space-colonization tree entries are disabled.

## Prior accepted gully scene

The preserved `right_dip_rise` profile supported one recursive fractal tree at
the bottom of a gully on a large, naturally undulating hillside. Do not destroy
or flatten this accepted profile while working on `flat_landform`.
The terrain is deliberately asymmetrical: it preserves the left fold while a
broad right-side dip falls and then rises again. Foreground grading retains a
partial slope instead of flattening the land into a rotated rectangle.

The tree is uniformly scaled by the new tree-level `scale` control. Its current
value is `2.5`; this finally gives the tree convincing physical proportion to the
nearby gully. The camera has been pulled as far back as practical inside the
existing foreground bounds and intentionally crops part of the crown.

That scene used one continuous placement layer with 3.4 million seven-blade
tufts (23.8 million blades). Blade height was `[8, 14]` before instance scale,
making an intentionally tall sward. Grass geometry exposes height, width,
segments, lean, bend, taper, droop, tuft construction, tropism, and a smooth
spatial tropism field in JSON. Preserve the named `030125` droop and `030551`
tropism looks in `scene_workspace/grass_presets.json`.

Important recent local renders:

- `030125`: tall grass with `[2, 6]` tip droop. Varied specular highlights read
  as direct morning light on the grass.
- `030551`: strong global tropism. Broader dark masses suggested late-afternoon
  light, but the foreground remained too uniformly directed.
- `031839`: extreme spatial tropism. Broad directional currents broke up the
  uniformly combed foreground.
- `041530`: tree at uniform scale `2.5`, before camera pullback.
- `042211`: pulled-back camera; tree proportions and visible crown improved.
- `043521`: direct fog/shaft diagnostic. Light and fog were overwhelmingly
  bright and noisy.
- `044355`: direct render with redesigned porous mask and reduced light. The
  physical gobo appeared as a black pixel-grid artifact in the upper-left sky;
  direct rendering is not suitable for this mask.
- `045140_composite`: artifact-free two-pass composite with softer mask. It read
  more like morning mist, but the openings merged into broad haze.
- `050947_composite`: open mask fraction reduced to 20.5% and redirected toward
  the gully. The user judged that there is still too much overall light while
  the actual shafts are too dim.

The grain/noise in the atmospheric renders is currently desirable. The user
explicitly said it supports an artistic formalism; do not raise sample count or
denoise it merely for technical cleanliness.

Relevant values for the preserved gully/composite state include:

- camera eye: `[545, 194, 695]`
- camera target: `[5, 230, -5]`
- camera FOV: `55`
- tree uniform scale: `2.5`
- `morning_sun.scale`: `5.0`
- `shaft_sun.scale`: `2.5`
- fog `sigma_s`: `0.00030`
- fog boundary radius: `1400`
- `sun_aperture.beam_target`: `[-250, 180, -130]`
- aperture outer radius: `700`
- aperture grid resolution: `224`
- aperture open fraction: approximately `20.5%`
- terrain size: `[1900.0, 1600.0]`
- terrain center: `[150.0, -100.0]`
- terrain resolution: `[401, 337]`
- hillside grade: `0.40`
- foreground leveling: start `0`, end `360`, minimum grade ratio `0.35`, target
  height `null`
- composite base opacity: `1.0`
- composite shaft opacity: `0.40`
- shaft-pass surface reflectance scale: `0.08`
- shaft-pass terrain reflectance scale: `0.015`

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
composite even though the user normally evaluates only `_composite.png`. The
physical cloud mask is visible to camera rays in a direct render, so present the
two-pass composite—not a direct fog/shaft render—as the intended result.

## Documentation policy

Documentation should evolve alongside functionality. Current focused documents
include:

- `docs/fractal-tree-configuration.md`
- `docs/terrain-configuration.md`
- `docs/atmosphere-configuration.md`
- `docs/lighting-configuration.md`
- `docs/shaft-compositing.md`

Research PDFs are local reference material and should not be pushed to GitHub.

### Continuity and handoff delivery

Every checkpoint that updates a continuity or handoff record must complete both
delivery steps before it is reported as finished:

1. Commit the updated record and push the active branch to GitHub.
2. Copy the current continuity/handoff record to the Google Drive session archive
   at `gdrive:wipImages/pbrt-v4/SessionArchive/`.

Confirm the Git commit, branch, and remotely stored Google Drive path to the user.
A GitHub push alone does not complete continuity delivery.

## Working preferences and safeguards

- Show render progress in a visible terminal.
- Keep the terminal open after completion; assume the user will close it.
- Use one approval only for the desktop terminal launch. Monitor logs and files
  with sandboxed read-only commands so the user is not asked repeatedly.
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

1. Establish explicit landscape/sky module boundaries and migrate the existing
   values within the one authoritative `scene_workspace/config.json`. Do not
   create another scene JSON or change accepted rendered behavior during the
   migration.
2. Add distant hills for the receding horizon and clouds through those new
   boundaries. These are required by the proof-of-concept composition and must
   be real modules rather than interface placeholders.
3. Continue extending the Python model and Qt inspector in response to artistic
   use; substantial generator and interface development remains expected.
4. Keep renderer implementations subordinate to artistic categories; in
   particular, never generalize the specific PBRT `rgbgrid` medium into an
   atmosphere name.
5. Preserve the accepted `053110` poppy baseline and the established grass,
   tree, terrain, and atmospheric work. Historical archive filenames remain
   unchanged and reproducible.
6. Preserve readable and raw conversation archives in the gitignored
   `SessionArchive/` directory.

## Conversation preservation

The source Codex event log for the multi-day session is stored outside the
repository under the user's `.codex/sessions` directory. A compressed immutable
snapshot and a readable visible-message transcript are stored in
`SessionArchive/`. The raw snapshot is authoritative and includes embedded
images and tool records. The Markdown transcript preserves the visible textual
conversation in chronological order and marks image positions.
