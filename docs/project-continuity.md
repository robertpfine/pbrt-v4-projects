# Project Continuity

Last updated: 2026-08-28

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
`rgbgrid-medium/config.json`; do not create per-landform JSON files. Terrain now
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
poppy `camera_frustum` block is enabled with a 2% frame margin and a conservative
local bounding radius of `0.95`. When poppies are enabled, `count: 2600` now
means 2,600 complete instances accepted inside the reduced camera frustum,
rather than 2,600 placements scattered across the whole terrain rectangle.
This constraint does not perform terrain-occlusion testing.

The last render before the frustum change is `022442`. Its archived PBRT did
contain 2,600 updated poppy instances, but only 793 instance origins fell inside
the camera frustum. No render has yet been made with the new camera-constrained
scatter.

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
tropism looks in `rgbgrid-medium/grass_presets.json`.

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

1. The next session changes artistic focus away from fog. The user judged the
   grass beautiful and its JSON infrastructure highly useful, but the cost of
   3.4 million tall tufts is not justified when fog hides their detail. Preserve
   the grass implementation and presets, but restore the earlier, less expensive
   short-pasture ground treatment for the active scene. This means changing the
   ground-cover treatment, not reverting the accepted current terrain shape,
   gully, camera, or 2.5 tree scale.
2. Systematically kick the tires on the four remaining entries under
   `scene.terrain.details`, using decisive rather than incremental tests:
   `surface`, `litter`, `rocks`, and `undergrowth`. `surface` is the texture and
   bump treatment attached directly to the terrain mesh; `litter`, `rocks`, and
   `undergrowth` are terrain-aware scattered geometry. Explore one control at a
   time with deliberately pronounced values, as was done for grass.
3. Fog/shaft work is paused at `050947_composite`: broad atmospheric brightness
   remains too high while localized shafts remain too dim. Intentional render
   noise should be preserved if this exploration resumes.
4. Continue broadening the modular scene system: procedural terrain types,
   skies/clouds, atmosphere, lighting controls, and reusable plant/tree
   components.
5. Eventually reorganize the organically grown `config.json`, but only after
   the current functional modules stabilize.
6. Preserve readable and raw conversation archives in the gitignored
   `SessionArchive/` directory.

## Conversation preservation

The source Codex event log for the multi-day session is stored outside the
repository under the user's `.codex/sessions` directory. A compressed immutable
snapshot and a readable visible-message transcript are stored in
`SessionArchive/`. The raw snapshot is authoritative and includes embedded
images and tool records. The Markdown transcript preserves the visible textual
conversation in chronological order and marks image positions.
