# Artist Questions and Answers

A running reference of questions the artist has asked and the settled
answers, grouped by topic so nothing has to be asked twice. Each entry is
the current answer; when something changes, the entry is rewritten rather
than appended to. This file belongs to the artist; Claude writes to it on
request, Codex reads it.

## Artist's criticisms (running; not yet acted on)

Recorded verbatim in substance as raised, 2026-09-07. No action taken on
any item until the artist finishes the round and says so.

1. **"Context" is a terrible descriptor.** It doesn't say what the panel
   holds.
2. **It should not be under Scene; it belongs under Setup.**
3. **Latitude, longitude, time zone, world north are noise at this
   stage.** The artist cares only about the scene name and the date.
4. **Mode should not be shown.** There are no alternative modes; a control
   with one choice is clutter.
5. **General:** Claude carried the JSON key name ("scene_context") straight
   into the interface instead of asking what the artist would call it —
   and did the same with the row's placement. Not as sharp as hoped.
6. **A landform page must show the whole landform.** Under `flat_landform`
   the artist expects `patches`, `topography` (including the noise
   controls), and `surface` (including texture) — everything the JSON has
   for that landform. The per-landform page shows only a subset.
7. **Governing rule, stated by the artist:** the GUI work is about *moving
   things around* — presenting what the JSON already has, where the artist
   wants it. Not rewriting, not truncating, not joining things together.
   Every field in the JSON for a thing appears on that thing's page.
8. **"Ground surface texture" is an invented row that leads nowhere.** It
   points at `landforms[i].surface.texture` and opens the old Ground page,
   which exposes only an Enabled box and a read-only mode label — none of
   the texture parameters — and is hardwired to the heightfield landform,
   not the selected one. The texture belongs on the landform's own page
   under `surface`, with all its fields; the separate row should go.
9. **Clicking "Land cover" shows the Context page.** The container row has
   no page, and the Studio's fallback for a missing page is the first page,
   Context. **Resolution (artist):** containers — Landforms, Land cover,
   Objects, Clouds, Atmosphere — are not clickable at all. They only
   expand and collapse, like Setup and Scene already do. No overview pages.
10. **Litter, rocks, and undergrowth have no page.** Clicking them opens
    their landform's page. Each is a full JSON entry (`construction`,
    `population`) and needs its own page showing all of it.
11. **The specification for what a page shows is the JSON entry itself.**
    The artist's example, undergrowth: `enabled`, `generator`, then
    `construction` (variants, scale, reflectance_variants) and
    `population` (seed, count, region center/size, max_slope_degrees,
    y_offset, exclusion center/radius, patchiness strength/frequency) —
    every field, grouped as the JSON groups them, in the JSON's order.
    Nothing chosen, nothing omitted. This is the standard for every page.
12. **Background page is a stub.** The JSON `sky.background` has `enabled`,
    `type`, `source`, `color_mode`, `color`, `scale`, and a 15-field
    `environment` block (generator, resolution, seed, coverage, softness,
    three feature fractions, horizon_bias, contrast, four colors,
    rotation_degrees). The page shows three fields.
13. **Sun page is a stub.** The JSON `sky.sun` has `enabled`, `type`,
    `from`, `to`, `color_mode`, `temperature`, `scale`,
    `use_astronomical_direction`, and the `light_shafts` block (light,
    aperture). Same standard as item 11 applies.
14. **Render page must mirror `render_settings` as the JSON groups it:**
    `film` (x_resolution, y_resolution), `sampler` (type, pixel_samples),
    `integrator` (type, max_depth), `backend` (type, show_statistics),
    `shaft_composite`. Today the page lists these fields but flat, without
    the JSON's groups, and mixes in `file_names` and `file_paths`, which
    are separate roots and not render settings.
15. **Shaft light / shaft composite: deferred.** Leave it out of this round
    entirely (Render page, Sun page, Scene Setup). To be dealt with later.
16. **"Every field, in the JSON's order" is the starting point, not the
    end state.** It supersedes the earlier recorded direction in
    `continuity.md` ("do not infer that every JSON value needs a permanent
    control"). Show everything first; curation, if any, comes later and is
    the artist's decision, made from a complete view.

**Resolved in Steps A and B (2026-09-07):** items 1–4, 6–15 — the entry
form builder renders every entry in JSON order; Context is gone; Setup
shows Scene (name, date), Camera, Render; containers are not clickable
(a Qt "current item" subtlety made Sky fall through to the first page — fixed);
shaft hidden everywhere; ground-texture row removed. Codex's page
functions remain in the code, unreachable, for Step C.

**Later observations, same session (resolved):**
- Page titles and top-level sections in capitals; nested sections indented.
- Fields too wide — fixed widths; a draggable divider between Parameter
  Values and the image viewer.
- Six trailing zeros — three decimals, or the value's own precision.
- Mouse wheel over a number box changed values (reflectance reached 10.13)
  — wheel disabled on every number box and dropdown.
- The heightfield rule should be stated in Scene Setup, not only enforced
  — note added under LANDFORMS; the two rows tagged "· heightfield".
- "0.62 is a hack? It should be in the JSON" — yes; logged under Deferred
  generator work.

## Deferred generator work

- **Undergrowth (fern) geometry is hard-coded.** `_fern_mesh()` in
  `scene_workspace/build_scene.py` (line ~2242) fixes frond count (5),
  spread (0.85), peak height (0.62), leaflet width/length in code; the JSON
  exposes only `construction.scale`. Should be lifted into `construction`
  the way grass blade proportions are (`construction.blade`). Rocks and
  litter likely the same. Also: the mesh is a placeholder that does not
  read as a fern up close — a better fern is a generator task.
- **Astronomical sun direction** from Context date/time/place (no solar
  code exists yet).
- **Ocean wave engine** (`water` is an empty placeholder).
- **Live oak** via `fractal_tree.py` with depth-scheduled `upward_bias`.

## Incidents

**2026-09-07 — PBRT refused the scene: "reflectance used as an albedo has
> 1 component."** Undergrowth `reflectance_variants` had become
`[0.025, 10.13, 0.03]` / `[0.04, −7.82, 0.04]` (from 0.13 / 0.18).
Cause: the entry page's number boxes stepped by 1.0 and responded to the
mouse wheel on hover, so scrolling the panel changed values. Reflectance
must be 0–1. Second gap: `scene_config.py` validates `reflectance` but not
`reflectance_variants`, so Save accepted it. Fix: restore 0.13 / 0.18;
number boxes to ignore the wheel unless focused and step in proportion to
the value; validator to range-check `reflectance_variants`.

## Glossary

- **Art Studio** — the Qt desktop application (`pbrt_v4_art_studio.py`)
  that edits `config.json`, launches renders, and shows the latest image.
  Always the full name; never "Studio" (too close to Visual Studio).
- **Outline** — the left panel of the Studio: the hierarchy of scene
  components you click to choose what to edit. (Never "tree".)
- **Parameter Values** — the right panel of the Studio, where values are
  edited. (Formerly "Inspector"; that name is retired.)
- **Scene Components and Setup** — the dialog shown before the workspace
  opens, where you choose which components are in the scene and set camera
  and render basics. Reopen it with the **Scene Setup…** toolbar button.
- **config.json** — `scene_workspace/config.json`, the one authoritative
  scene file. Everything the Studio shows comes from it; everything a
  render uses comes from it.
- **Working copy** — the files on disk in `~/my-pbrt-projects`, the ones
  you, Codex, and Claude edit. Git's own term is "working tree"; we don't
  use it, to avoid the plant.
- **Checkpoint** — a Git commit plus push to GitHub plus a
  `docs/continuity.md` update, done by Codex on your instruction.
- **Fixture** — a frozen reference file the automated tests run against,
  so that tests never depend on your working `config.json`.
- **CLI tool** — a program run by typing a command in a terminal rather
  than clicking in a window (`git`, `rclone`, `python3`).
- **tree** — a plant.
- **Entry** — one named block in `config.json` at its outermost braces:
  each item of `landforms[]`, `surface_objects[]`, `objects[]`,
  `clouds[]`, `fog[]`, `rain[]`; the single blocks `background`, `sun`,
  `water`, `camera_settings`, `render_settings`. An entry is one Outline
  row and one page. The brace-groups nested inside it are the sections of
  that page.
- **Container** — an Outline row that only groups entries (Landforms, Land
  cover, Objects, Clouds, Atmosphere). Not clickable; expands and
  collapses only.

## The Studio

**Q: What are the parts of the Art Studio window?**
Toolbar across the top (Validate, Save Scene, Render, Stop, Refresh Image,
Reload JSON, Scene Setup…). Below it, left to right: the Outline, Parameter
Values, and the image viewer, which takes the remaining width. The
Persistent Render Log docks along the bottom; a one-line status bar sits
under it.

**Q: Do I have to press Save Scene before rendering?**
No. Render saves first, then launches the pipeline. Save Scene is for
keeping changes without rendering — before Reload JSON, before closing, or
after Scene Setup… so component choices stick.

**Q: What does Save Scene do?**
Validates the whole scene, then writes only the values you changed into
`config.json`, leaving the rest of the file exactly as it was, including
your manual formatting. It refuses if the file was edited outside the
Studio since it was loaded, so nothing is silently overwritten.

**Q: Do Render and Save Scene both write to config.json?**
Yes, the same way. Render calls Save Scene internally before doing
anything else. There is no separate "render save."

**Q: Why doesn't the image update after a render from the terminal?**
The viewer refreshes itself only when a render started from the Studio
finishes. For renders run through `./run_render_terminal.sh`, press
**Refresh Image** on the toolbar; it loads the newest PNG in the local
archive.

**Q: How do I add a component that isn't showing in the Outline?**
The Outline shows only enabled components — nothing is dimmed or hidden in
place. Open **Scene Setup…**, check the component, press Done. The Outline
rebuilds.

**Q: Why won't the workspace open, or Validate fail, with "exactly one
enabled terrain_heightfield landform"?**
`right_dip_rise` and `flat_landform` are both terrain-heightfield
landforms and the scene allows only one of them on at a time. The Scene
Setup dialog now treats them as a pair: checking one unchecks the other.
`vista_plane` and `broad_rise` are not heightfields and are independent.

**Q: Can the Studio add a new component (a second sunflower, an ocean)?**
No. The dialog can only turn on entries that already exist in
`config.json`. Creating a new entry is a JSON edit, by hand or by Codex.
An "add" catalogue was deliberately excluded from the Studio's design.

**Q: Where do file names and paths get set?**
Not in Scene Setup — by design. They follow the back-end convention
(archive names derive from the scene name). They remain editable on the
Render page in Parameter Values if ever needed.

**Q: Can we have sliders?**
Yes, cheaply. Every numeric control comes from one function, `_number()`;
adding a slider there upgrades every numeric field at once. The real work
is choosing a sensible range per field — some ranges today are
placeholders like 0…1,000,000, which make a slider meaningless. Not yet
built.

## config.json

**Q: What are the five root keys?**
`file_names`, `file_paths`, `camera_settings`, `render_settings`,
`scene_description`.

**Q: How far does scene_description reach?**
From line 54 to the end of the file — about 97% of it. The first four
roots are setup; `scene_description` is the scene itself: `scene_context`,
`landforms[]`, `objects[]`, `sky`, `atmosphere`, `water`.

**Q: Is the Context date the render date, or a calendar date that fixes
the sun's position?**
The latter, by design — `date`, `local_time`, `time_zone`, `latitude`,
`longitude`, and `world_north` describe a real moment at a real place, from
which the sun's azimuth and elevation follow. But the wiring is not
finished: `sky.sun.use_astronomical_direction` exists and is `false`, and
no solar-position code exists yet, so the sun still comes from the
explicit `from`/`to` vectors under `sky.sun`. The 5 AM sunrise poppy
scene's vector was computed by hand. Connecting date to sun position is a
contained, not-yet-built task.

**Q: Should there be a generic landform (elevation 0) that can be created
under a new name from the Studio?** *(Tabled 2026-09-07 — revisit.)*
Proposed and deferred. It would be the Studio's first "add" — creating an
entry in `config.json` rather than enabling one — which the original spec
excluded deliberately. Sketch when revisited: a template (not a
`config.json` entry) — plane patch, topography off, meadow-green
material, mild texture, empty cover; **New Landform…** stamps a copy into
`landforms[]` under a given name, and naming is the promotion (no
provisional state; `enabled:false` already serves). Open technical
question: appending to `landforms[]` must not reformat the whole block —
check `scene_config.py`'s span parser for a surgical insert first.
Sequence after the land-cover mapping; it writes to the file, so it's a
different risk class.

**Q: "rocks · on flat_landform" — can rocks only appear on flat_landform?
What if I want poppies on broad_rise?**
The suffix states where that entry sits *now*: inside that landform's
`surface_objects` in `config.json`. Because ownership is by nesting, the
entry renders only when that landform is enabled. Poppies on `broad_rise`
today: the poppies page has POPULATION › `extension`, already targeted at
`broad_rise` (off) — it scatters a second population of the same poppies
there. Grass has the same. An *independent* poppy entry on another
landform requires copying the block in the JSON until the land-cover
migration adds a `landform` field to each entry.

**Q: What if more than one landform is enabled? What renders?**
Each enabled landform is built and rendered as its own ground at its own
position; they coexist (the canonical scene has `flat_landform` and
`vista_plane` on together, and `broad_rise` joined them in the hill
renders). The one rule: only one **terrain-heightfield** landform may be
on — `right_dip_rise` or `flat_landform`, not both — because the cover and
terrain-following placement assume a single heightfield. Scene Setup
enforces this as a radio pair and now states it under LANDFORMS, and tags
the two rows "· heightfield". Overlapping landforms simply intersect.

**Q: How do I control height off the ground?**
Camera height: `camera_settings.look_at.eye`, the Y value. A plant's
height above the terrain: `population.y_offset` (small; keeps it from
sinking into the mesh). A plant's size: `construction.scale`, which is
uniform — taller and wider together. The undergrowth mesh's own
proportions (0.62 peak height, 0.85 spread) are hard-coded in
`build_scene.py` `_fern_mesh()`; see Deferred generator work.

**Q: Does making the Studio friendlier require changing config.json?**
No. Every Outline and dialog change is presentation only. `config.json`
stays the sole authority for parameter values; the Studio is a view onto
it and must never hold a parallel copy of the state.

## Git, checkpoints, and tests

**Q: What is a "live" scene versus an "exploratory" one?**
Live = `config.json` as it is on disk right now, whatever you last saved.
Exploratory was Claude's shorthand for "different from what is committed
in Git." Neither is wrong; one is checked in and the other isn't yet.

**Q: What are "tests," and why did they go red when I saved a scene?**
About 160 small automated checks in `tests/` that open the Studio
invisibly and confirm the code behaves; Claude runs them after every
change (about six seconds). They used to read your working `config.json`
and assert specific values, so saving a different scene made them fail
for no real reason. Fixed on 2026-09-07: value assertions now use the
frozen fixture `tests/fixtures/canonical_config.json`. One test still reads
the live file and checks only that it validates and has the five root
keys. You can save and render whatever you like.

**Q: After Claude commits, does Codex have to pull?**
No. Codex and Claude share one local checkout — one folder, one Git
history. A commit is immediately visible to both; a push only copies it
to GitHub. A pull is needed only if a commit exists on GitHub but not
here, which would require one of us to work from a different clone.
What the other assistant needs after a commit is awareness: re-read
`git status` and `git log` before acting.

**Q: Who commits?**
Codex, on your instruction ("checkpoint"). Claude edits when told to and
does not commit or push unless you explicitly grant it. Rules are agreed
in advance for if you do: commit only on instruction; `git status` and
`git pull --ff-only` first; only Claude's own changes; never rewrite
history, force-push, or touch `main`; Co-Authored-By trailer.

## Working with Codex and Claude

**Q: Both sessions are open — can they collide?**
Only if both work at the same moment. Rule: whoever you are instructing
holds the pen; the other doesn't touch the working copy or Git. Guard,
both directions: before editing or committing, check `git status`; if it
shows changes you didn't make, the other assistant was active — stop and
ask. After either commits, the other re-reads `git status` and `git log`.

**Q: Which handoff file is authoritative?**
`docs/continuity.md`, written by Codex. `AGENTS.md` is Codex's bootstrap.
`docs/claude-review-continuity.md` is Claude's review journal, not a
second authority; if the two disagree, `continuity.md` wins and the
disagreement goes to you. One author per record. Things Claude finds
reach the official record by you relaying them to Codex.

**Q: How often will Claude check with me during a task?**
Once, at the start of a distinct instruction (no builder, PBRT, or Codex
activity in progress), then straight through to the end without further
check-ins. A new instruction is a new check. Not per minute, not per file.

**Q: Will Claude render?**
Yes, when a task needs it — via `./run_render_terminal.sh` so the GNOME
terminal is visible. Claude flags first only for unusually large renders
or anything resembling the known "death loop."

**Q: Sonnet 5 or Fable 5.1?**
Fable 5.1 is the more capable, 5× more expensive model. Bounded,
well-specified work (the Studio changes so far) is Sonnet-tier; save Fable
for genuinely fuzzy problems such as the live-oak geometry. Your `/model`
default is Fable; a running session keeps the model it started on.

**Q: How do I see usage on the Pro plan?**
`/cost` in the Claude Code input for the current session; claude.ai →
Settings → Usage for the plan's limits and reset time.

## Tools

**Q: What is a CLI tool? What is rclone?**
A CLI tool is run by typing a command in a terminal. `rclone` is one for
copying files to cloud storage; Codex already uses it to mirror
`continuity.md` to Google Drive. It is a program plus a config file of
named "remotes," not a running service — nothing to "share"; both
assistants could invoke the same installed program. A separate remote
with Google's `drive.file` scope would give the folder-limited Drive
access you asked for; the claude.ai Drive connector cannot be scoped to
one folder.

**Q: Why did flatpak/snap fail in the VS Code terminal but work in a
separate terminal?**
VS Code runs as a Snap and leaks Snap environment variables into its
integrated terminal, which breaks programs like `flatpak`. A plain GNOME
Terminal is clean. `run_render_terminal.sh` already strips those
variables for the same reason.

**Q: Zettlr — desktop icon without restarting?**
Installed via Flatpak. A launcher was added at
`~/.local/share/applications/zettlr.desktop`, so it appears in Activities
without logging out. The icon may look generic until your next login.
