# Space Colonization Project Continuity

Last updated: 2026-08-20

## Current checkpoint

- Branch: `space-colonization`
- Accepted Git checkpoint: `c95a3af` (`Add grove instancing and sunset water composition`)
- Local and remote branches were synchronized at that checkpoint.
- Accepted render: `Archive/rgbgrid-medium_20260819_194855.png`
- The user explicitly described that image as perfect and requested that nothing be
  changed at that point.

The `Archive/` directory is intentionally ignored by Git. Render bundles are also
copied to the configured Google Drive destination by `render_pipeline.sh`.

## Project intent

The tree began as an effort to approximate the architecture of Figure 8 in the
2007 Runions space-colonization paper, using the 2008 Runions thesis for additional
implementation context. Fidelity is judged primarily by the resulting visual tree
architecture, not by reproducing undocumented parameters literally.

The project has since expanded from a single Figure 8-inspired tree into:

- a seven-tree grove made from transformed instances of one generated tree;
- procedural foliage based on generated branch geometry;
- configurable sky/environment color;
- low-angle sunlight and a reflective ground/water treatment;
- portrait and aerial camera experiments.

## Accepted tree architecture

The active tree configuration is in `rgbgrid-medium/config.json`. Important choices
include:

- `D = 1.0`
- `d_k = 5D`
- `d_i = infinity`, represented by `di_multiplier: null`
- 5000 initial attraction points
- 500 maximum growth loops
- five continuously injected attraction points per iteration
- injected-point birth distance decreasing from `20D` to `5D`
- upward tropism strength `0.35`
- a prescribed straight trunk of `120D` before crown growth
- an effectively unbounded attraction-point placement mode used to avoid a
  sphere-shell crown appearance
- pipe-model, age-based, and support-weighted branch thickening
- post-growth path simplification/smoothing and dominant-axis trunk blending

The result has a strong trunk, several supporting limbs, dense vertical crown
development, fine twigs, and smooth taper. Do not casually replace this topology
with render-only branch straightening; earlier tests reintroduced strained angles.

## Foliage

Foliage generation is implemented in `foliage.py` and controlled by the active
tree's `foliage` block in `rgbgrid-medium/config.json`.

Current important values:

- foliage enabled
- deterministic seed `7`
- internode spacing `5D`
- maximum 12000 leaves
- current leaf scale `4D`
- base ovate leaf dimensions `1.0D x 0.4D`, producing effective dimensions
  `4.0D x 1.6D`
- several deterministic green/yellow blade colors

Generated foliage is split into reusable object definitions and placement files so
the same foliage can inherit each grove instance's transform.

## Grove

`rgbgrid-medium/build_scene.py` defines generated wood once and instances it using
the `scene.grove` configuration. Seven placements currently vary translation,
Y rotation, and uniform scale. Foliage placements inherit the same instance
transform. The grove is intentionally compact; the user did not want the crowns
expanded farther merely to increase apparent density.

## Accepted lighting, water, and camera state

At checkpoint `c95a3af`, the accepted image uses:

- a 4:5 portrait film at `2400 x 3000`;
- camera eye `[0, 60, 1700]`, looking at `[0, 180, -430]`;
- a blue RGB infinite environment light at scale `0.60`;
- an active 2700 K distant sun at about 2 degrees elevation and scale `6.0`;
- a large reflective conductor ground disk with neutral reflectance `0.98` and
  roughness `0.012`.

This creates a clearly demarcated water/ground line, intense golden illumination,
long blue shadows, and fine sunset glitter on the reflective surface. The effect is
stylized rather than physically literal, and the user explicitly preferred it over
the smoother mirror-reflection experiments.

Important historical correction: an earlier attempt to warm the sun accidentally
changed a disabled spotlight while the active distant light remained at 5500 K.
The accepted checkpoint correctly applies 2700 K to the active distant light.

## Rendering workflow

Run:

```bash
./render_pipeline.sh rgbgrid-medium
```

The machine has an NVIDIA RTX 5090 and CUDA rendering is fast enough for iterative
full-resolution tests. The user prefers seeing the live pipeline output in a visible
GNOME Terminal. Because VS Code runs as a Snap, launch GNOME Terminal with a clean
environment to avoid Snap/GLIBC conflicts. The working invocation used during this
session was equivalent to:

```bash
env -i \
  HOME=/home/rpf4 USER=rpf4 \
  PATH=/usr/local/cuda-11.8/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  DISPLAY="$DISPLAY" WAYLAND_DISPLAY="$WAYLAND_DISPLAY" \
  XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
  DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" \
  XAUTHORITY="$XAUTHORITY" \
  LD_LIBRARY_PATH=/usr/local/cuda-11.8/lib64 \
  gnome-terminal --wait -- bash -c \
  'cd /home/rpf4/my-pbrt-projects; ./render_pipeline.sh rgbgrid-medium'
```

## Source material and local-only files

The authoritative local references are ignored by Git:

- `docs/SpaceColonizationAlgorithm_Runion.pdf`
- `docs/runionsa.th2008.pdf`
- `docs/TheAlgorithmicBeautyOfPlants.pdf`

Other intentionally untracked local items include `Gallery/`, `space_col.py.bak`,
and the obsolete root-level continuity note named `Continuity — Session 2026-05-26:`.
Do not include those items in commits unless the user explicitly changes this policy.

## Suggested next-session procedure

1. Read this note and inspect commit `c95a3af` before making changes.
2. Show or review the accepted render before proposing a new visual direction.
3. Preserve the accepted configuration as the baseline; make one controlled visual
   change per render whenever practical.
4. Continue using visible-terminal renders.
5. Establish and push Git checkpoints after the user accepts a meaningful state.

