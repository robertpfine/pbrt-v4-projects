# Claude Code Review Continuity

This is Claude Code's own handoff record, maintained separately from Codex's
canonical `docs/continuity.md`. A new Claude session in this repository
should read this file after reading `docs/continuity.md`, not instead of it.
This file exists so review context survives between Claude sessions without
editing Codex's authoritative record.

## 2026-09-07 checkpoint handoff (updated by Codex)

The artist's final instruction assigns the combined checkpoint to Codex,
including Claude's GUI/test work and this journal, the artist's `guiTest`
configuration edits, and the shared-checkout protocol. Codex reviewed the
changes; the Qt suite completed 158 tests with 19 dependency skips and no
failures. The live configuration and frozen test fixture validate. See the
September 7 checkpoint section in `continuity.md` for current scene identity,
verification details, and limitations.

The role protocol in `AGENTS.md` and `continuity.md` is current: only one
assistant works at a time; inspect `git status` before editing or committing,
and stop for artist direction on another assistant's unacknowledged changes.
After either assistant commits, the other reads `git status` and `git log`
before doing anything. Claude edits when instructed and commits or pushes
only with an explicit artist grant; Codex is the default checkpoint committer.
Earlier dated statements below describe the permissions and uncommitted state
at those sessions, not the state after this checkpoint.

## Role and protocol (historical September 5 record)

The artist installed Claude Code in the VS Code environment as a second set
of eyes for independent review. This is recorded in the artist's own
`docs/continuity.md` (commit `7ec5268`, "Record artist preference for
independent Claude review"): Claude's findings are welcome and should be
evaluated against the same code, configuration, and archived render
evidence, but this does not transfer implementation authority to Claude or
replace the artist's decisions.

On 2026-09-05 the artist explicitly resolved the open coordination question
that record had left pending: **Codex remains the sole committer.** Claude
does not commit or push to Git under any circumstance, does not edit
`scene_workspace/config.json` or any generator source, and does not run the
render pipeline, build scripts, or test suite without the artist's specific
in-the-moment instruction. Claude's output is findings, recommendations, and
records like this one — never repository state changes made on its own
initiative.

Because Claude does not commit, this file itself is uncommitted after each
session that writes it. Whether to bring it under version control is the
artist's and Codex's call, not Claude's.

## 2026-09-05 first handoff

### Repository state at session start

- Branch `pbrt-v4-art-studio`, up to date with `origin/pbrt-v4-art-studio`.
- Working tree was dirty at the start of the session: uncommitted
  `sky_environment.py` (new), `tests/test_sky_environment.py` (new), and
  modifications to `scene_config.py`, `scene_workspace/build_scene.py`,
  `scene_workspace/config.json`, `tests/test_scene_config.py`.
- That work implemented a deterministic seamless procedural-overcast
  environment map (PBRT equal-area mapping, layered broad/medium/detail
  directional noise, written as linear-RGB `.pfm` + sRGB preview PNG) wired
  into `write_lights()` via a new `environment_filename` /
  `environment_rotation_degrees` path for the PBRT `infinite` light, with
  matching `scene_config.py` validation.
- Assessment: this coheres exactly with `docs/continuity.md`'s own stated
  direction after the rejected spherical-shell proof (`d5f920b`) — a proper
  environment map at infinity for distant sky, bounded volumes only for
  local clouds, mirroring the documented Blender World/Volume separation
  research. No drift from the documented plan was found.
- By session end, Codex had committed that work (commits `cf65fd4`,
  `339bb98`, `7ec5268`); the working tree was clean again. No render was
  observed to have been launched or evaluated during this review session.

### Design discussions this session (not implemented — advisory only)

Two open architectural questions were discussed at the artist's request, no
code was written:

**Ocean wave generator.** `scene_description.water` is currently
`{"enabled": false}` with no generator — a from-scratch design. Recommended
approach: a static Gerstner/trochoidal wave-summation height field evaluated
once per render (this project renders stills, not animated sequences, so a
full FFT ocean spectrum like Tessendorf's is unnecessary complexity for now).
Implement as a new `topography.generator` (e.g. `"ocean_gerstner"`) on a
`water` landform, paralleling the existing `distant_ridge` height-field
generator and reusing `sky_environment.py`'s layered broad/medium/detail
frequency-summation idiom. Whitecap/foam via the same thresholded-noise
pattern already used for cloud coverage. Prototype standalone first (a
`water_preview.py`, mirroring `poppy_preview.py` /
`cloud_boundary_diagnostic.py`) before wiring into the live config.

**Qt GUI formal buildout.** Confirmed by reading `pbrt_v4_art_studio.py`:
the `Inspector` class currently has one hand-built `_build_X_page()` method
per section (grass, poppy, tree, sky, clouds, distant_hills, camera, render,
etc.) — no schema-driven form generation exists yet, and there is no water
page. Recommendation: do not move to full reflection/auto-generated forms —
that would conflict with the artist's explicit principle that not every JSON
value warrants a permanent control. Instead, once 2-3 more generators exist
and the per-page copy-paste (e.g. in `_build_distant_hills_page`) becomes
clearly repetitive, extract a lightweight declarative per-generator
field-spec (path, type, range, group) that shares widget-building code
(slider+spinbox pairing, vector rows, search/filter) while keeping which
fields appear and how they're grouped a deliberate per-page decision. Every
page, existing or new, must keep routing saves through `scene_config.py`'s
targeted value-span `set()` / `save()` so manual JSON editing is never
compromised — confirmed this is the actual save mechanism by reading
`scene_config.py` rather than assuming it from `docs/continuity.md`'s
description alone.

### Nothing pending

No open questions blocking the artist's return. No code changes were made
by Claude this session. No render was requested of or launched by Claude.

## 2026-09-06 second handoff

No code changes, commits, or renders this session either. This was working-
relationship calibration plus one substantive design discussion. Repository
state unchanged from end of first handoff (branch `pbrt-v4-art-studio`
clean, `HEAD` at `7ec5268` at session start).

### Working-relationship items resolved

- **Check-in cadence for future build tasks**: one check at the start of a
  distinct instruction (verify no builder/PBRT process already active, per
  `docs/continuity.md`'s own existing safeguard), not a check per minute or
  per file. A single instruction's worth of work — write code, test, render,
  report back — runs without further check-ins until the artist gives a new
  instruction.
- **Rendering is in-scope for an assigned build task**, not something
  requiring separate permission each time. If given a task like the wave
  generator or a live-oak retune, using `./run_render_terminal.sh` to
  validate it is implicit in the task — flag before proceeding only for
  unusually large/costly renders or anything resembling the documented
  "death loop" failure mode, not for ordinary low-sample test renders.
- **Artist's iteration workflow confirmed and saved to Claude's cross-project
  memory** (not repo-local): task → code + tests → visible-terminal render →
  inspect local `Archive/` → critique → repeat, regardless of which
  assistant (Codex or Claude) is doing the work.
- **Hypothetical-only discussion**: what shared Git/Drive privileges between
  Codex and Claude would mechanically look like. Nothing adopted. Key
  findings for if this is revisited: (1) Git push/commit access isn't a
  separate technical grant — Codex and Claude already share the same local
  checkout and git credential, so "commit privileges" is purely a behavioral
  permission, not an access-control change, and every commit in this repo
  (Codex's included) is already authored under the artist's own git identity;
  (2) for Drive, reusing Codex's existing `rclone` remote is simpler than a
  second claude.ai-side OAuth grant, and a *new*, separately-scoped `rclone`
  remote using the `drive.file` OAuth scope would come closer to true
  folder-only access than either alternative.
- **Google Drive backup for this file**: the artist created a Drive folder
  "SessionArchive - CLAUDE" for Claude's handoffs (see
  `~/.claude/projects/-home-rpf4-my-pbrt-projects/memory/gdrive_claude_handoff_folder.md`
  in Claude's cross-project memory). No working write path exists yet —
  claude.ai's Google Drive connector was unauthenticated in-session, and even
  authorized it's unconfirmed whether it's folder-scoped or supports
  uploads. This file stays local/uncommitted until that's resolved.
- **Communication preferences** (saved to Claude's cross-project memory,
  `language_preferences.md`): never use the word "schlepping"; no
  anthropomorphizing narration of process before/between tool calls ("Let me
  look at...", "I'm checking...") — direct answers and results only, no
  commentary on "thought process." Also configured in
  `~/.claude/settings.json`: `disableRemoteControl: true`, `spinnerVerbs`
  pinned to a single fixed word ("Processing") instead of the rotating
  default set, `spinnerTipsEnabled: false`. These are Claude Code app
  settings, not project files — noted here only because they shape how
  future sessions should communicate with this artist.

### Config.json / Qt GUI review (advisory only, nothing implemented)

Read `pbrt_v4_art_studio.py` and the live `scene_workspace/config.json`
structure in response to the artist's request for thoughts on making the Qt
GUI more manageable. Confirmed:

- `config.json` is 1939 lines, 5 root keys; `scene_description` has 8 keys
  including 4 landforms and 3 independent objects.
- The Qt `Inspector` already has a two-level `QTreeWidget` nav driving a
  `QStackedWidget`, and a shared widget-primitive layer (`_check`, `_text`,
  `_choice`, `_number`, `_pair`, `_vector`) that every page routes through —
  each already wired to live-refresh and to `scene_config.py`'s targeted
  `set()`/`save()`. This is more mature than "voluminous JSON, ad hoc GUI"
  first suggests.
- Three concrete gaps identified: (1) no `QGroupBox`/collapsible sections
  anywhere — every page is one flat scrolling form; (2) multi-instance
  sections (4 landforms, likely 4 clouds, 3 objects) concatenate into one
  long page instead of getting per-instance nav children, even though
  `_build_landform_page` already loops `config.landform_names()` — the data
  supports it, the nav doesn't yet; (3) a real structural inconsistency —
  Grass/Poppies/Trees/Ground pages hardcode `surface_object_path("grass")` /
  `terrain_landform_index()` to one implicit landform, while the Landform
  page itself iterates all of them. This conflicts with the artist's own
  documented "choose a landform first, then see what's on it" principle
  already recorded in `docs/continuity.md`, and would matter as soon as a
  second landform gets its own surface objects (e.g. an ocean landform).
- Confirmed with the artist: none of this requires any `config.json` schema
  change — it's presentation-layer only, consistent with the project's own
  "GUI must not create parallel configuration state" rule. `config.json`
  remains the sole authoritative document for parameter values.
- **Proposed first step, not yet started**: collapsible `QGroupBox` sections
  on the Sky page only (the most voluminous single page), as a low-stakes
  calibration task — no schema change, no render needed to validate (just
  launch `./run_art_studio.sh` and look), fully reversible. Awaiting the
  artist's go-ahead on which page to start with.

### Live oak / fractal_tree.py discussion (advisory only, nothing implemented)

The artist asked about live oak (*Quercus virginiana*) branching form and
whether fractal techniques could succeed where past attempts failed.
Established facts, now also in Claude's cross-project memory
(`live_oak_generator_history.md`):

- `lsystem.py`'s `live_oak()` — a sophisticated proprioception/momentum/
  phototropism scaffold-growth simulation — and earlier space-colonization
  work were both **artistic failures**, per the artist directly: "neither
  realistic nor artistic," a geometry problem, not a rendering/material one.
  `live_oak` is currently disabled in the live scene; `fractal_tree` (a
  different, unrelated generator) is active in its place.
- Read `fractal_tree.py` in full: it's a Da Vinci's-rule / pipe-model
  recursive branching fractal (`r1^α + r2^α = rp^α` at every fork, recursion
  terminating by radius rather than fixed depth), already praised in
  `docs/continuity.md` as the strongest tree-like result to date.
  Recommended it as a more promising foundation for live oak specifically
  than either failed approach, because it gives direct, low-dimensional,
  orthogonal control (angle/length-ratio per branch order) rather than
  emergent behavior from a competitive point cloud or multi-force
  integration — exactly the property that makes a failure diagnosable and
  fixable.
- Identified one specific, concrete mismatch by reading the code:
  `upward_bias` in `fractal_tree.py` is a flat constant applied at every
  tilt, every recursion depth, biasing the whole tree toward an upright/
  conical mass from the first split onward. Live oak needs the opposite
  early on — a long near-horizontal run before curling upward only near
  limb tips. Proposed making this bias depth-scheduled instead of constant —
  a small, targeted change to one function (`tilted()`), not a rewrite.
  Nothing in `fractal_tree.py` has been touched.
- Published an Artifact, "Live Oak Branch Study"
  (https://claude.ai/code/artifact/0e1bac7d-39b5-42d9-88eb-88ce52d02156): a
  hand-authored algorithmic sketch (small deterministic 2D recursive
  function mirroring the real dominant/lateral split mechanism, with an
  authored bias schedule) comparing the current default silhouette against
  the proposed live-oak direction, plus the parameter-delta table. Built
  from the code mechanism and the botanical description discussed in
  conversation — explicitly **not** derived from reference photographs, and
  explicitly not a PBRT render or preview of actual output.

### Nothing pending

No open questions blocking the artist's return. Two proposals await a
go-ahead: the Sky-page `QGroupBox` calibration task, and the
`fractal_tree.py` `upward_bias` scheduling change for a live-oak attempt.
Neither has been started.

## 2026-09-07 first build session: Art Studio Outline and Scene Setup

First session in which Claude edited code, each step on an explicit "Go"
from the artist. All changes are in `pbrt_v4_art_studio.py` and `tests/`;
`config.json` (other than the artist's own saves from the Studio),
`scene_config.py`, and every page builder are untouched. 158 tests pass.

### Vocabulary (artist-chosen; see Claude memory `art_studio_gui_vocabulary`)

- **Outline** — the left panel of the Studio (Qt `QTreeWidget`); header now
  reads OUTLINE.
- **Parameter Values** — the right panel of editable controls; header added.
- **working copy** — the files on disk in the repository (Git's "working
  tree"). Never say "tree" for either: a tree is a plant.

### What was built, in order

1. **Outline restructured** to mirror `config.json`'s two kinds of root:
   `Setup` (Camera, Render) and `Scene` (Context, Landforms, Objects, Sky →
   Background/Clouds/Sun, Atmosphere, Water). Heading rows are not
   selectable. `_build_navigation()` only.
2. **Layout**: Outline | Parameter Values | image viewer, left to right, the
   viewer taking the remaining width. `_build_layout()` only.
3. **Scene Components and Setup dialog** (`SceneSetupDialog`), shown before
   the workspace opens (like an image editor's new-document dialog) and
   reopenable from a new **Scene Setup…** toolbar action. Left column SETUP:
   scene name, camera eye/look/up/FOV, film size, pixel samples, max path
   depth, backend, shaft composite. Right column SCENE COMPONENTS: every
   named entry under `scene_description` as a checkbox bound to its
   `enabled` flag, generated from the JSON arrays (`scene_components()`),
   surface objects nested under their landform. File names and paths are
   deliberately absent — the artist wants those governed by back-end
   convention, with full control over camera and render.
4. **Outline is generated from the JSON and shows enabled components only**
   (`visible_components()`). No dimming — the artist's explicit choice;
   components are re-enabled through Scene Setup…. Grouping rows with
   nothing enabled beneath them (Clouds, Objects, Atmosphere, Water today)
   are omitted. Outline rebuilds after the dialog closes and after Reload
   JSON. `StudioWindow` now accepts a preloaded `SceneConfig` so the
   dialog's unsaved choices carry into the workspace.
5. **Terrain-heightfield radio group** in the dialog: `right_dip_rise` and
   `flat_landform` cannot both be on (the scene's own rule,
   `scene_config.terrain_landform_index`); `vista_plane` and `broad_rise`
   are independent. Added after the artist hit the validator error.
6. **Refresh Image** toolbar action: reloads the newest archive PNG on
   demand — needed because renders run through `run_render_terminal.sh`
   never updated the viewer.
7. **Test fixture**: `tests/fixtures/canonical_config.json`, a frozen copy of
   the committed Poppy Field scene. Tests that assert specific values now
   read it instead of the live `config.json`, so saving or rendering an
   exploratory scene from the Studio no longer turns tests red. One test
   still reads the live file and checks only that it validates and has the
   five root keys. **Maintenance note for Codex:** if the config schema
   migrates again, update the fixture alongside it.

### Facts learned that are not in the code

- The Studio's **Render** action saves first (`start_render` →
  `save_config`), so the artist never needs Save Scene before rendering.
- `pkill -f pbrt_v4_art_studio.py` from a Claude Bash call kills Claude's
  own shell (the pattern matches the command line). Kill by exact python
  path via `pgrep -f "^…/.venv/bin/python …/pbrt_v4_art_studio.py"`.
- Launching the Studio from a Claude/VS Code shell needs the same Snap
  variable cleanup `run_render_terminal.sh` performs, or Qt fails on GLIBC.
- The full suite hangs silently if any test closes a `StudioWindow` with
  unsaved changes: `closeEvent` opens a modal "Save the scene before
  closing?" box that never returns offscreen. Reload the config before
  closing in tests.

### Working agreements reached this session

- **Commit/push authority: still with Codex ("hold").** The artist is
  inclined to grant it later; the operating rules were agreed in advance:
  commit only on explicit instruction, `git status` + `git pull --ff-only`
  first, commit only what Claude changed, never rewrite history or
  force-push or touch `main`, Co-Authored-By trailer.
- **Concurrency guard, in effect now, both directions:** before editing or
  committing, check whether the working copy contains changes you did not
  make; if so, the other assistant has been active — stop and ask the
  artist. After either assistant commits, the other re-reads `git status`
  and `git log` before doing anything. Both sessions are typically open at
  once; only one works at a time — whoever the artist is instructing.
- Codex and Claude share one local checkout; a Claude commit needs no pull
  by Codex, only awareness. The artist is relaying this to Codex for
  `AGENTS.md` (Core safeguards) and `docs/continuity.md`.
- **Record ownership:** `AGENTS.md` and `docs/continuity.md` are Codex's;
  this file is Claude's review journal, not a second authority. If the two
  ever disagree, `continuity.md` wins and the disagreement goes to the
  artist.

### Open proposals (not started)

- Per-instance pages: clicking `flat_landform` in the Outline should show
  only that landform (today it opens the concatenated Landform page);
  likewise surface objects, clouds, objects.
- Sky page exposure: sun, environment map, cloud-grid builder exist in the
  JSON but not in Parameter Values.
- Sliders paired with the exact spin boxes, via `_number()` once, then
  per-field ranges.
- `fractal_tree.py` depth-scheduled `upward_bias` for a live-oak attempt;
  sketch published as the "Live Oak Branch Study" artifact.

### State at handoff

Working copy: Claude's changes above plus the artist's `config.json` save
(scene name `guiTest`, `right_dip_rise` on, `flat_landform` off), all
uncommitted. The artist is asking Codex to review and checkpoint everything.
Art Studio may still be running from Claude's last launch.
