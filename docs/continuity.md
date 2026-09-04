# PBRT-v4 Art Studio Continuity

Last updated: 2026-09-04

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
- Active branch: `pbrt-v4-art-studio`
- Remote: `https://github.com/robertpfine/pbrt-v4-projects.git`
- Current visual-system checkpoints:
  - `5ae191a` (`Checkpoint accepted poppy field scene systems`)
  - `573f8b8` (`Add configurable pasture terrain and grass tropism`)
  - `4fa4e9c` (`Add spatial grass tropism and cloud shaft controls`)
  - `95d8b44` (`Add PBRT-v4 Art Studio proof of concept`)
  - `5cb45e8` (`Refine poppy framing and Art Studio render feedback`)
  - `6c796b4` (`Establish landscape and sky module boundaries`)
  - `73694c8` (`Checkpoint horizon studies before height-field reset`)
- Primary working scene: `scene_workspace/config.json`
- Renderer: PBRT-v4 with CUDA/GPU rendering
- Normal pipeline entry point: `./render_pipeline.sh`
- Shaft-composite entry point: `python3 render_shaft_composite.py`

The `pbrt-v4-art-studio` branch was created from clean Step 3 checkpoint
`2143b0b`. The earlier `space-colonization` branch remains intact as the
historical development line for that tree system. New application-level GUI,
configuration, landscape, sky, atmosphere, and rendering work belongs on
`pbrt-v4-art-studio`.

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
- `file_names` now owns the PBRT, working-image, and archive-image names.
- `file_paths` now owns scene outputs, local and remote archives, and the PBRT
  executable.
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
`run_art_studio.sh` starts the interface. The complete 23-test suite passes,
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
selects one named entry with `scene.landscape.ground.active_landform`. The named
`right_dip_rise` and `flat_landform` profiles contain landform geometry only,
while the material, surface treatment, and five instanced detail layers remain
shared siblings under `scene.landscape.ground`. The active profile is currently
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

## 2026-08-30 landscape and sky boundary migration

Step 3 of the agreed proof-of-concept sequence is implemented without creating
a second configuration file. The one authoritative JSON now has these explicit
module boundaries:

- `scene.landscape.ground` contains the complete accepted ground system formerly
  stored at `scene.terrain`.
- `scene.landscape.water` is present and disabled pending the third Step 4
  implementation element: water bodies, waves, optics, and shoreline behavior.
- `scene.landscape.distant_hills` is present and disabled pending its generator.
- `scene.sky.background` contains the accepted neutral infinite environment
  formerly stored as the first entry in `scene.lights`.
- `scene.sky.clouds` is present and disabled pending its generator.
- `scene.lights` now contains only the remaining point, spot, and distant lights.

The builder reconstructs the original PBRT light ordering by writing the sky
background before the remaining lights. After migration, rebuilding the full
3.4-million-tuft scene produced the exact same 936,127,421-byte PBRT file and
SHA-256 hash as before migration:
`dfb1781890823c10da1d483358294748d3d2ad2db767a168e24c54774f88a929`.
This is a byte-for-byte behavior-preservation check; no GPU render was needed.

Tree, grove, and planar-phyllotaxis arrays retain their established paths. The
relationship among reusable source objects, scene instances, and creation
processes remains explicitly deferred and was not decided indirectly during
this bounded migration. See `docs/scene-module-boundaries.md`.

## 2026-08-31 pre-refactor distant-hills checkpoint

Git checkpoint `73694c8` preserves the current working state before replacing the first
distant-hills implementation. It is recoverable evidence of the composition and
experiments, but the artist has explicitly rejected its ridge-band construction
as the direction for further development.

The current composition uses:

- camera eye `[388, 165, 491]`, target `[5, 155, -5]`, and FOV `50`;
- film resolution `2000 x 1450`;
- the active `flat_landform` with zero grade and zero landform noise;
- preview grass density of 340,000 seven-blade tufts;
- 2,600 established poppies framed by their primary flowers;
- no fog;
- a low 4600 K sun behind the camera at `[35, 14, 45]`;
- an `intermediate_field`, experimental `distant_hills` ridge band, and a
  sparse 260-instance horizon tree population.

The horizon-tree experiment in render `022305` replaces the former continuous
white row with dark foliage colors, irregular gaps, 70% rounded deciduous
forms, and 30% narrower tiered evergreens. The tree work may be retained as a
separate horizon-vegetation capability, but it must not remain conceptually
embedded inside the replacement hill landform. The poppy color definitions
were not changed; their brighter variation in recent renders came from the
frontal sunlight.

The experimental distant-hills implementation added deterministic triangular
terrain bands, explicit peaks, a later 21-point `ridge_profile`, Perlin
irregularity, and softened shading normals. It produced a conspicuous hard
contour where the solid ridge met the sky. The artist clarified that an
algorithmic control profile may exist internally, but the rendered image must
not read as though the ridge has been outlined. Repeated correction of that
band architecture accumulated too many mechanisms and is now superseded.

The approved next direction is a deliberate restart with simpler objectives:

1. Replace the ridge-band and prescribed-skyline model with one continuous 3D
   height-field surface whose elevation varies across both width and depth.
2. Begin with one broad, low, off-center rise beyond the meadow. Establish only
   its distance, scale, perspective, color, and natural meeting with the sky.
3. Do not begin with multiple depth ranges, an authored visible outline,
   atmosphere, fog, or decorative complexity.
4. Move horizon vegetation outside the distant-hills landform module before
   rebuilding it further.
5. Add further landform variation only after the simple initial surface is
   artistically understood and accepted.

The artist explicitly requested this checkpoint before the replacement begins.
Do not treat render `022305` or the current `ridge_profile` as an accepted hill
design merely because they are preserved here.

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

- `docs/artistic-tool-vision.md`
- `docs/qt-proof-of-concept-specification.md`
- `docs/scene-module-boundaries.md`
- `docs/config-schema-new-scene.md`
- `docs/fractal-tree-configuration.md`
- `docs/terrain-configuration.md`
- `docs/atmosphere-configuration.md`
- `docs/rain-configuration.md`
- `docs/lighting-configuration.md`
- `docs/shaft-compositing.md`

Research PDFs are local reference material and should not be pushed to GitHub.

### New-thread continuity protocol

The repository-root `AGENTS.md` is the automatic bootstrap for Codex. It exists
to route every new thread here; it does not duplicate or replace this record.

Every new Codex thread working in this repository must read this complete
`docs/continuity.md` file first. It is the canonical current handoff and takes
precedence over every earlier or specialized record. Reading only the final
"Immediate follow-up work" section is insufficient because accepted visual
states, workflow safeguards, naming decisions, and archive obligations appear
throughout this file.

After reading this file, use the following routing rather than assuming that a
specialized document is obsolete or that a historical document is current:

1. Read `docs/artistic-tool-vision.md` and
   `docs/qt-proof-of-concept-specification.md` for the artist-approved purpose,
   terminology, hierarchy, and interaction model.
2. Read `docs/scene-module-boundaries.md` before changing the live JSON
   hierarchy or implementing landscape, distant-hill, sky, or cloud modules.
3. Read the focused configuration guide for any subsystem being changed:
   terrain, atmosphere, lighting, shaft compositing, or fractal trees.
4. Read `docs/space-colonization-continuity.md` before resuming detailed
   space-colonization tree or grove work. It is a subordinate subsystem record;
   its old branch and scene state do not override this canonical handoff.
5. Treat `HANDOFF.md`, `HANDOFF05262026.md`, `HANDOFF_05252026.md`, and
   `HANDOFF_05242026.md` as historical evidence from May 2026. Consult them when
   tracing earlier pipeline decisions, PBRT lessons, or branch history, but do
   not use their active-work, branch, configuration-path, or next-step claims as
   current instructions.
6. Consult the gitignored `SessionArchive/` transcript and raw session snapshot
   only when the canonical and routed documents do not resolve an ambiguity.

The canonical Google Drive copy is
`gdrive:wipImages/pbrt-v4/SessionArchive/continuity.md`. A new thread with access
to the repository should use the committed local copy first because it travels
with the active branch; the Drive copy is the external handoff backup.

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
- Launch that visible terminal with `./run_render_terminal.sh`. This repository
  wrapper is the canonical interactive render entry point from Codex/VS Code:
  it removes the Snap-injected GTK/GIO runtime variables that otherwise make a
  raw `gnome-terminal` launch fail with a GLIBC symbol error, preserves the
  desktop and CUDA environment, runs `./render_pipeline.sh`, and keeps the
  terminal open when the pipeline exits. Do not substitute a raw
  `gnome-terminal` command and do not use XTerm; XTerm is too small for the
  artist's progress view. Before invoking the wrapper, verify that no builder,
  PBRT process, or render pipeline is already active, and launch exactly one.
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
  the active `pbrt-v4-art-studio` branch.

## Immediate follow-up work

Detailed implementation notes, exact benchmark results, test coverage, and the
remaining pre-migration gate are recorded in
`docs/engineering-progress-2026-09-04.md`.

The active artist-accepted high-resolution master is render `093054`, with
`091401` retained as its accepted development-resolution checkpoint and
`054517` as the accepted clear-atmosphere predecessor. Do not automatically
restore the disabled `broad_rise`. The next session should proceed in this
order:

1. **Validate the ground-level new-scene schema.** The approved, non-runnable
   architectural design is `docs/config-schema-new-scene.md`. All fourteen
   review issues are resolved. Its engineering translation is
   `docs/config-schema-new-scene-ground-level.md`; it defines fields,
   validation, generator ownership, current-to-proposed paths, and the
   normalized C++ cloud-grid contract. It is documentation, not a second live
   configuration, and does not require the artist to audit every generator
   leaf. Escalate only choices that change visible terminology, artistic-control
   location, or scene-building workflow.
2. **Preserve the accepted sunrise master.** `093054` is the active visual
   master at `8000 x 5800`, 512 samples per pixel, and integrator depth `200`.
   Its warm cloud illumination, dark dew-coated field, and low horizon mist are
   accepted together. The retained hill, grass extension, and poppy extension
   remain reversible inactive alternatives. Grass placement still needs
   off-screen buffers at the left and right frustum borders, analogous to the
   existing bottom margin; preserve the accepted composition while making that
   bounded correction.
3. **Render-input snapshotting is implemented.** `render_snapshot.py` now
   freezes the JSON and participating generator sources before any build begins.
   Both the standard and shaft-composite paths build and render from that frozen
   repository mirror, then archive those exact inputs with SHA-256 manifests.
   Manual live-JSON edits during a render affect only the next run. Failed runs
   retain their temporary workspace for diagnosis; successful runs remove it
   only after local archival and configured remote synchronization.
4. **Migrate only after the prototype schema is approved.** Tackle accumulated
   size, repetition,
   naming, and organization in the single authoritative
   `scene_workspace/config.json`. Preserve direct manual editing, do not create
   a second live scene configuration, and refactor the working file in tested,
   usable stages rather than building a disconnected replacement. Move one
   complete artistic object at a time without keeping duplicate live values;
   update its builder, GUI, validation, and all operational consumers together.
   Preserve the artist's earlier C++ configuration mental model: camera and
   render controls are immediately discoverable, and each visible object's
   geometry, placement, material, color, and surface objects remain
   adjacent. Begin from the landform-first principle: choose a landform, then
   decide its relief, appearance, and surface objects.
   The first live migration stage is complete: `file_names` and `file_paths`
   are active, their old paths are absent, every known consumer uses the new
   locations, and a bounded rebuild reproduced the pre-migration PBRT scene
   byte for byte. The next stage moves camera controls to `camera_settings`.
5. **Overcast and rain remain exploratory.** The live configuration is no
   longer the accepted sunrise master. It contains an unaccepted overcast deck
   extension and disabled rain-curtain experiment. Do not render or tune that
   state automatically on return; see the dated checkpoint section below.
6. **Qt workflow.** Reconsider the GUI around actual artistic use: exact manual
   editing, discoverable scene inspection, rendering, progress visibility, and
   comparison of accepted images. Do not infer that every JSON value needs a
   permanent control.
7. **The compiled cloud-grid accelerator is implemented.** The standalone C++
   helper receives a normalized versioned job from Python, supports both
   current cloud forms, writes `uniformgrid` or `rgbgrid` PBRT declarations,
   and uses deterministic CPU multithreading. Small-grid density and optical
   parity tests pass against the Python reference at the existing five-decimal
   PBRT precision, and Python remains the configured fallback. The live legacy
   cloud block has only a small adjacent technical `grid_builder` switch; no
   artistic cloud values moved. The current 160×40×120 overcast grid builds
   768,000 voxels in about 0.55 seconds automatically threaded versus about
   5.77 seconds in the Python reference before text formatting. A frozen full
   scene build took about 208.70 seconds and produced a 1.044 GB PBRT file,
   confirming that current vegetation/scene expansion is now the larger build
   cost. Do not confuse either build time with PBRT `volpath` render time.
   The required limited visual comparison is now complete with the artist's
   explicit authorization. Python control `020525` and C++ comparison `020829`
   used the same full current overcast grid at bounded render settings and
   produced byte-for-byte identical PNGs. The live configuration was restored
   exactly afterward. See `docs/cpp-cloud-grid-validation-2026-09-04.md`.

Additional continuity requirements:

8. Preserve `scene.landscape.ground` and `scene.sky.background` as the migrated
   homes of the accepted ground system and neutral infinite sky respectively.
   Do not create another scene JSON or change accepted rendered behavior.
9. Continue extending the Python model and Qt inspector in response to artistic
   use; substantial generator and interface development remains expected.
10. Keep renderer implementations subordinate to artistic categories; in
   particular, never generalize the specific PBRT `rgbgrid` medium into an
   atmosphere name.
11. Preserve the accepted `053110` poppy baseline and the established grass,
   tree, terrain, and atmospheric work. Historical archive filenames remain
   unchanged and reproducible.
12. Preserve readable and raw conversation archives in the gitignored
   `SessionArchive/` directory.

## 2026-09-04 first live configuration-migration stage

The first staged migration is implemented in the sole authoritative
`scene_workspace/config.json`. Its first two root sections are now
`file_names` and `file_paths`. The old top-level `archive` object,
`runtime.pbrt_binary`, `pipeline.rclone_sync`, `scene.master_file`,
`scene.output_filename`, and `scene.generated_medium` are absent; there are no
duplicate compatibility readers. A configured remote archive now means that
ordinary and composite workflows attempt synchronization only after the local
bundle is complete, retaining local output on remote failure.

The render pipeline, immutable snapshot transaction, standard builder,
shaft-composite workflow, tree and foliage generators, validator, and Qt
inspector all use the new paths. Exact filename and path values remain manually
editable and are also exposed on the Qt Render page. A bounded migrated build
using the archived `020525` diagnostic values produced the exact same
117,462,947-byte PBRT scene and SHA-256
`c82109823574ffb2365758988f1832052811f274eedd51db05003e7863cfbc64` as the
pre-migration builder. No PBRT render was launched for this structural check.
See `docs/config-migration-progress-2026-09-04.md` for the detailed record.

The next migration stage is camera settings. Preserve the existing camera
values exactly, remove `scene.camera`, and update the builder, terrain-aware
placement, validator, and Qt inspector together before proceeding to render
settings.

## 2026-09-03 schema and overcast-work checkpoint

The artist and assistant began the separate architectural draft
`docs/config-schema-new-scene.md`. It documents only
`scene_description.mode: "new"`; it is not a runnable configuration and does
not replace the one authoritative live `scene_workspace/config.json`. The live
file has not yet migrated to this proposal.

The approved first four configuration sections are `file_names`, `file_paths`,
`camera_settings`, and `render_settings`, followed by `scene_description`.
Within a new scene, multiple independently enabled landforms are supported.
Each landform owns its placement, geometry patches, shared topography, one
material, one configurable surface-texture system, and a flat
`surface_objects` collection. The discarded word `contents` was too vague.

The following schema decisions are approved:

- `primitive` retains its conventional graphics meaning. Constituent landform
  surfaces are `patches`; a `plane` is an Art Studio mesh generator rather than
  a claimed native PBRT-v4 plane shape.
- One landform may contain multiple patches, but its topography is one shared
  elevation system evaluated across them. Different elevation or material
  behavior normally means a separate landform.
- A rectangular plane patch is sufficient initially. Triangle, trapezoid, and
  other polygonal footprints may be added to the plane generator over time.
- There is no generic landform `boundary` block. Geometry extent, population
  regions, texture edge effects, and future inter-landform transitions remain
  separate responsibilities.
- Surface means material plus texture. Each landform has one material. Its
  surface texture may combine multiple named noise patterns, but topographic
  noise remains distinct because it changes actual elevation.
- `scene_description.objects` contains independently placed geometry such as a
  surreal sphere. Direct `pbrt_shape` selection remains distinct from an Art
  Studio `generator`.
- `construction` defines one generated form and `population` places copies by
  `scatter` or `explicit` methods. This applies to grass: construction defines
  one tuft and population count specifies tufts, not blades.
- Every current generator and population control—including bend, angles,
  tropism, frustum, and variation settings—will move intact during prototype
  migration without field-by-field review. Detailed internal rationalization
  follows after the hierarchy works.
- Permanent taxonomy within `surface_objects` is deferred to `2gen`. Mountains,
  cliffs, and large rock formations are landforms or landform features;
  discrete boulders and stones may be surface objects.
- Water is a visible disabled `Yes_PH` module beside landforms, objects, sky,
  and atmosphere. No speculative water controls are added yet.
- Every cloud under `sky.clouds` becomes self-contained: placement and bounds,
  density-field construction, and medium optical controls. Existing values
  move intact; shared cloud defaults do not survive the migration.
- Atmosphere retains fog, haze, mist, and rain categories. Fog and rain are
  implemented systems whose controls move intact. Haze and mist remain empty
  placeholders until developed. Clouds remain exclusively under sky.

Issue 10 is approved. `scene_context` holds date, local time, IANA time-zone
name, latitude, longitude, and world north. The boolean
`sun.use_astronomical_direction` selects the sole active direction source:
`true` derives it from the scene context, while `false` uses the explicit PBRT
`from` and `to` values. Existing scenes initially migrate in explicit mode to
preserve their appearance. Sun color/temperature and scale, and infinite-sky
color and scale, remain explicit artistic controls.

Issue 11 is approved. A blank scene initializes an enabled perspective camera
at `[0,2,10]`, looking at the origin with positive Y up and a 50-degree field of
view. Its enabled PBRT `infinite` background uses neutral RGB `[1,1,1]` at scale
`1`, and its directional sun begins disabled. These initialization values do
not replace the camera or sky settings of migrated scenes. Issues 12–14 were
subsequently resolved as recorded below.

Issue 12 is approved for the prototype, subject to validation during migration.
The existing `shaft_composite` pass and combination controls move under
`render_settings`; light and aperture construction remain with the sun under
`scene_description.sky`. Disabling the block produces an ordinary single PBRT
render. Enabling it produces the base pass, shaft pass, and final composite,
with both diagnostic passes retained as mandatory reproducibility evidence.
Issues 13–14 were subsequently resolved as recorded below.

Issue 13 is approved. A render receives one timestamp and identifier, and its
configuration and required source inputs are frozen before the builder reads
them. The local archive receives the completed reproducibility bundle first;
that bundle is then copied to the configured Google Drive archive. Snapshotting
is mandatory application behavior without a disable switch. GitHub remains a
separate development checkpoint destination for source, JSON, and documentation
only—not rendered PNG or generated PBRT files. Issue 14 is resolved below.

Issue 14 is approved, completing the architectural review. Before live paths
move, complete the ground-level schema, implement mandatory input snapshotting,
and implement the standalone CPU C++ cloud density-grid generator through
deterministic Python equivalence and limited visual validation. Migration then
moves filenames and paths, camera, render settings, the `scene_description`
shell, individual landforms and surface-object generators, independent objects,
sky components, atmosphere components, and the disabled water placeholder.
Obsolete legacy paths and temporary compatibility code are removed last. The
single live config remains authoritative; every stage moves rather than
duplicates values, updates the builder, validator, and Qt inspector together,
preserves existing appearance, and receives testing, structural PBRT comparison,
and a stable Git checkpoint.

The rain-curtain implementation in `rain.py` is present and disabled in the
live configuration. It uses vertically coherent 3D fractal noise, bounded
heterogeneous media, and explicit optics and placement. No rain render has been
accepted. The render pipeline archives `rain.py` with reproducibility bundles.

The overcast experiment remains unresolved. `022819` was the artist's preferred
comparison among the early overcast studies, not a final accepted master.
Completed renders `155247` and `160043` verified that the ordinary PBRT progress
display and render process still work at cloud grid resolution `[160,40,120]`.
Render `160043` extended the deck from depth `11000` to `21000`, but still
showed a visible horizon gap/split rather than filling the sky.

The live config now contains the later unaccepted corrective experiment:
overcast-deck center `[-15000,850,-10000]`, size `[50000,800,26000]`, resolution
`[160,40,120]`, and a depth slope lowering its far end by `300`. The associated
render was canceled after impractical progress behavior. No render is active at
this checkpoint. The current generated `scene.pbrt` and live config must not be
mistaken for an accepted visual state. Use archived input bundles when
reproducing `093054`, `091401`, `054517`, `022819`, `155247`, or `160043`.

Checkpoint validation passes. The repository-local Qt environment runs all 59
discovered tests successfully with five NumPy/Pillow-dependent tests skipped;
those three atmosphere and two vista-texture tests pass separately under the
production Python environment. The live JSON parses successfully, both render
shell entry points pass `bash -n`, and no builder, PBRT process, or render
pipeline is active.

## 2026-09-01 accepted 093054 high-resolution master

Render `Poppy_Field_at_Sunrise_20260901_093054.png` is the artist-accepted
high-resolution master of the 5:00 AM sunrise-mist composition. The artist
described it as “absolutely stunning” and explicitly requested preservation.
Configuration checkpoint `395fe09` records its `8000 x 5800` film resolution.

The master retains the accepted 091401 atmosphere and composition while adding
the artist's manual production settings:

- scene name `Poppy Field at Sunrise`, which produces the descriptive archive
  stem rather than `untitled_landscape`;
- film resolution `8000 x 5800`—46.4 million pixels and exactly 16 times the
  pixel count of the `2000 x 1450` development render;
- Halton sampling at 512 samples per pixel;
- volumetric path depth `200` rather than the earlier development value `80`.

The master was inspected locally through a temporary downsampled viewing copy;
the original 78,408,119-byte PNG was not modified. Its archived JSON and the
live/committed configuration match exactly at SHA-256
`24017f437111007f354e9c0d14ec32a1b2c54b1d0c09989fb86512e31fce3fde`.
The archived and live builder match at SHA-256
`b9bc0e3fd62110b6cbc8153b9e946a49af503a95b7d288f527ad23c1c61bff9a`.
The accepted master PNG hash is
`692472e5dd534c5e646ff2135f046bf54bdeea1a2e3c7bdde1c65b4ac6848c85`,
and its PBRT hash is
`3d8d41ffac449aac5a821757936a5dfffff067e0671d831a11395343d0ce70b2`.
The archived PBRT independently confirms resolution `8000 x 5800`, integrator
depth `200`, and both cloud volumes returning to the surrounding `fog` medium.

Keep `091401` as the faster accepted development-resolution comparison. The
live configuration now intentionally remains at the high-resolution production
settings; lower it manually for exploratory renders rather than assuming the
master should be overwritten.

## 2026-09-01 accepted 5:00 AM sunrise-mist checkpoint

Render `091401` is the artist-accepted visual checkpoint for the first
time-based atmosphere study. The artist described it as “really nice” and
explicitly requested that it be preserved. Implementation checkpoint `626bdbc`
contains the fog-height falloff, dew material support, nested-medium correction,
tests, and focused documentation.

The artistic assumptions are a due-south view at 43 degrees north latitude on
June 21, with the artist specifying sunrise at 4:19 AM and the rendered scene at
5:00 AM. The current scene uses:

- a distant sun at `[97.9,9.8,-18.3]`, corresponding approximately to 5.6
  degrees elevation and 63 degrees azimuth from north;
- 4000 K direct sunlight at scale `6.0`, giving both cumulus volumes restrained
  warm sunrise illumination;
- the uniform infinite sky at scale `0.055`, reduced from the earlier `0.22`
  clear-sky state;
- heterogeneous residual fog with `sigma_s: 0.00024`, `sigma_a: 0.000003`, and
  `g: 0.35`;
- a `[72,24,96]` Perlin fog grid with base density `0.28`, contrast `0.60`, and
  a smooth world-height fade from full density at Y `4` to zero at Y `90` with
  exponent `1.4`;
- a thin `coateddiffuse` grass surface with roughness `0.07`, eta `1.33`, and
  thickness `0.003` as the first restrained dew approximation;
- all 3,400,000 foreground grass tufts and 3,500 poppies from the accepted
  meadow composition;
- the vista plane's revised muted olive-gray base reflectance
  `[0.25,0.27,0.17]`; its existing mottle coverage, contrast, and mottle colors
  were not changed.

Enabling the fog first exposed a nested-medium error in diagnostic render
`090336`: a bright rectangular cloud-boundary artifact crossed the right cloud.
Cloud boundaries had returned rays to vacuum even while enclosed by the fog
volume. The builder now writes each cloud with `fog` as its exterior medium
when atmosphere is enabled, and the enlarged finite fog sphere contains both
cloud formations. `091401` verifies that the rectangle is gone. Do not treat
`090336` as an accepted image.

The exact archived `091401` JSON is preserved at SHA-256
`d291a591c05ee01a232158565469f45689170fe480831db8f30df16826d88ee5`.
The archived and live scene builder match at SHA-256
`b9bc0e3fd62110b6cbc8153b9e946a49af503a95b7d288f527ad23c1c61bff9a`.
The accepted PNG hash is
`890ab886c2a57c4cff3e4e24647628c1bea8d4ff2c9677d215fac7f2012cf8ab`.
All 52 repository tests pass with five dependency-aware skips in the Qt virtual
environment; the three atmosphere tests also pass under the production Python
environment used by the renderer.

During the approval window for implementation commit `626bdbc`, the artist's
post-render scene-name change to `Poppy Field at Sunrise` and integrator-depth
change from `80` to `200` entered the staged configuration. Therefore
`626bdbc` is the implementation checkpoint but is not a byte-identical config
checkpoint for `091401`; use the archived 091401 JSON for exact reproduction.
The later accepted `093054` master intentionally incorporates those settings
plus the `8000 x 5800` film resolution.

## 2026-09-01 poppy-field, cloud, vista, and grass checkpoint

Render `054517` is the artist-accepted endpoint of the current poppy-field
session. The artist described it as “really nice” and asked to stop for several
hours. The live `scene_workspace/config.json` matches its archived JSON exactly
at SHA-256
`2bfac63237035c811174a4fe265df3c81ae639ca70e86e0d6af1cb05312163f1`.
The archived PBRT contains no distant-hill, distant-grass, or distant-poppy
blocks.

The accepted composition currently uses:

- camera eye `[290,165,365]`, target `[5,155,-5]`, and FOV `50`;
- the flat meadow landform at `[-400,-700]`, size `[3000,2800]`;
- 3,400,000 seven-blade foreground grass tufts with blade height `[8,12]`;
- the artist's stronger manual grass shaping: lean `[0.10,0.48]`, bend
  `[-0.255,0.255]`, bend exponent `3.45`, tropism direction `465`, strength
  `[3,10]`, eight field octaves, and tuft angle jitter `38`;
- `camera_frustum.bottom_margin: 0.08` for grass, allowing off-screen roots to
  carry blades through the bottom of the image instead of making a hard edge;
- 3,500 foreground poppies, framed by their primary flowers, with their former
  far-depth fade disabled so they continue to the meadow horizon;
- three left-side recursive-fractal tree instances at Z `-8000`, `-9000`, and
  `-10000`; the three small middle-horizon trees were removed;
- the enabled mottled vista plane and the two enabled cumulus volumes;
- the complete `broad_rise` distant-hill configuration retained but the module
  switch set to `false`.

Although `054517` is accepted, close inspection reveals subtle left- and
right-edge grass boundaries because only the bottom frustum currently has an
off-screen placement margin. The next grass-placement adjustment should add
horizontal side buffers so growth continues beyond both image borders. This is
recorded for the return session and is not applied to the checkpoint itself.

The ground-detail architecture now permits `grass.extension` and
`poppies.extension` to scatter their own reusable objects directly on a named
distant-hill height field. The retained inactive values target `broad_rise`:
2,500,000 smaller grass tufts and 2,500 smaller poppies, both fading before the
crest. Render `053150` is the first verified hill-on image containing foreground
and hill poppies. The artist then requested the hill-disabled comparison and
preferred `054517`.

The simple cloud module is implemented in `clouds.py` as bounded PBRT media with
designed lobes, 3D Perlin fractal sums, domain warp, density modulation, and a
darker underside through separate absorption/scattering grids. The artist chose
the `025537` resolution balance—left `[120,72,48]`, right `[128,80,52]`—after a
four-times-denser test. Render `023731` is rejected as a whole-sky cloud design,
but its soft horizontal fragment remains a useful future horizon-cloud idea.

The large plane under `scene.geometry[0]` is enabled as `vista_plane`. Its base
diffuse color `[0.35,0.60,1.00]` is scaled by `0.22`, and
`vista_surface_texture.py` generates a deterministic 2048-square clustered
mottle intended to suggest distant habitation. Renders `033404` and `034523`
established this direction; the artist called `034523` great. The plane's
current placement inside the generic geometry array is an acknowledged example
of why the future configuration refactor must be holistic and landform-first.

Do not use renders `051939` or `054050` as reproducibility checkpoints. In both
cases an older in-flight builder generated PBRT from already-loaded state, then
the pipeline copied newer live JSON/source files into the timestamped archive.
`054050` therefore claims the hill is disabled in JSON while its PBRT still
contains `broad_rise`, 2,500,000 distant grass instances, and 2,500 distant
poppies. `054517` was explicitly checked for matching JSON and PBRT content and
is the valid accepted bundle.

## 2026-08-31 simple distant-rise baseline

Render `034256` is the artist-accepted baseline for the distant-hills restart.
The former four-band configuration, authored ridge profile, intermediate field,
and embedded horizon tree line have been removed from the live
`scene.landscape.distant_hills` module. The replacement contains one enabled
`broad_rise` height-field layer with one broad off-center peak and restrained
subordinate noise. Its reflectance exactly matches the primary ground material
at `[0.10, 0.17, 0.045]`. The clear infinite background is now sky blue with
color `[0.35, 0.60, 1.00]` and scale `0.22`; fog remains disabled.

The next experiment places two or three copies of the accepted recursive
fractal tree from the fog and light-shaft studies near the meadow horizon. This
is a bounded composition experiment, not a return to the rejected procedural
horizon tree line and not an extension of the distant-hills module.

## 2026-08-31 accepted tree-depth composition

Render `054100` is the artist-accepted endpoint of the initial fractal-tree
instancing and depth study. The live configuration matches its archived JSON
exactly. Six copies of one reusable fractal-tree definition are written through
PBRT object instancing; tree-level scale remains `2.5`, and every instance keeps
an independent position, Y rotation, and optional scale.

The accepted composition has three nearer trees grouped at the left at Z
positions `-8000`, `-9000`, and `-10000`, plus three visibly separated trees
near the middle at Z positions `-18000`, `-19000`, and `-20000`. Automatic
terrain placement is disabled so the manually authored Y coordinates remain
effective even though these trees lie beyond the finite meadow mesh.

The artist particularly values the way the left crowns peak over the visible
horizon while most of their trunks remain concealed. This implies a downslope
beyond the crest without directly showing that landform and is an important
depth cue to preserve. Do not "correct" the hidden trunks merely because the
trees are not attached to visible geometry.

Render `043645` is also intentionally preserved as an interesting exploratory
result. It extended the flat ground to encompass trees as far away as Z
`-20000`, creating broad horizontal ground layers. That extension was not the
requested placement method and is not the live configuration, but the image
should not be discarded.

The instancing implementation lives in `write_lsystem_trees()` and preserves
the prior single-origin behavior when an entry has no `instances` array. The
focused instancing tests verify local reusable geometry, manual translations,
per-instance scaling, and rejection of non-positive scales.

## Artist-approved landform workflow principle

The refactored configuration must follow the artist's landform-first working
model. The artist first chooses a landform; in the simplest case it is a plane.
After that plane exists, the artist decides whether it remains flat or becomes
hilly, assigns its color and surface treatment, and chooses what belongs on it,
such as grass and poppies.

This principle is critical and persistent. The underlying plane must not be
hidden as unrelated renderer scaffolding while its relief, material, and
surface objects are scattered across conceptually disconnected configuration
areas.
Manual editing must make the relationship easy to discover. Multiple scene
elements—including the current poppy meadow, broad rise, and a possible
detail-free vista plane beyond the ridge—may all be understood as landforms.
They can have different controls; this principle does not yet dictate the final
JSON nesting or require a universal landform schema.

## Conversation preservation

The source Codex event log for the multi-day session is stored outside the
repository under the user's `.codex/sessions` directory. A compressed immutable
snapshot and a readable visible-message transcript are stored in
`SessionArchive/`. The raw snapshot is authoritative and includes embedded
images and tool records. The Markdown transcript preserves the visible textual
conversation in chronological order and marks image positions.
