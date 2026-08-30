# Fractal Tree Configuration Guide

This guide documents the `fractal_tree` preset implemented in
[`fractal_tree.py`](../fractal_tree.py) and rendered through
[`scene_workspace/build_scene.py`](../scene_workspace/build_scene.py).

The configuration lives in an entry under:

```text
scene -> lsystem_trees -> an entry whose preset is "fractal_tree"
```

The current entry is:

```json
{
  "enabled": true,
  "preset": "fractal_tree",
  "origin": [0.0, -55.0, 0.0],
  "debug_render": { "mode": "cylinders" },
  "seed": 23,
  "trunk_height": 85.0,
  "trunk_segments": 20,
  "base_radius": 8.0,
  "crown_radius": 6.2,
  "initial_length": 34.0,
  "alpha": 2.2,
  "min_radius": 0.60,
  "max_depth": 12,
  "dominant_length_ratio": 0.76,
  "lateral_length_ratio": 0.62,
  "dominant_angle": 24.0,
  "lateral_angle": 48.0,
  "upward_bias": 0.18,
  "angle_jitter": 12.0,
  "length_jitter": 0.10,
  "asymmetry_min": 1.05,
  "asymmetry_max": 1.55,
  "leaves_enabled": true,
  "leaf_length": 2.8,
  "leaf_width": 0.72,
  "crownlet": {
    "style": "open",
    "depth": 4,
    "length": 10.8,
    "length_ratio": 0.75,
    "angle": 40.0,
    "radius_ratio": 0.46,
    "clustered_spread_ratio": 0.30,
    "clustered_length_ratio": 0.62,
    "leaves_per_tip": 8
  },
  "wood_reflectance": [0.20, 0.085, 0.020],
  "foliage_reflectance": [0.020, 0.18, 0.035]
}
```

The numerical examples below use these values. Distances and radii are in the
scene's ordinary world-space units.

## Preset selection and placement

### `enabled`

Controls whether this tree entry is generated and written into the PBRT scene.

- `true`: generate and render it.
- `false`: skip it without deleting its settings.

### `preset`

Selects the generator dispatched by `build_scene.py`. It must be
`"fractal_tree"` for the controls in this guide to apply.

### `origin`

Adds an `[x, y, z]` translation to every generated segment and leaf.

The current `[0.0, -55.0, 0.0]` moves the complete tree 55 units downward. It
does not alter growth, proportions, the seed, or branch directions.

### `debug_render.mode`

Controls how non-leaf segments are written.

- `"cylinders"` uses each segment's calculated radius hierarchy.
- `"curves"` uses the constant `debug_render.width` and is useful for schematic
  views, but it hides the calculated thickness hierarchy.

In cylinder mode, each segment is currently a constant-radius cylinder whose
radius is the average of that segment's starting and ending radii. Taper is
therefore visible across successive segments, not continuously within one
segment.

## Reproducible variation

### `seed`

Seeds a local deterministic random-number generator. It affects:

- structural radius asymmetry;
- branch-angle jitter;
- structural length jitter;
- crownlet angle and length variation;
- leaf orientations.

The same seed and all the same parameters reproduce the same geometry. Changing
the seed produces a sibling form rather than changing one isolated property.

## Trunk controls

### `trunk_height`

Sets the vertical distance from the tree's local origin to the crown-leader
attachment point. The current value is `85.0`.

Increasing it lengthens the clear trunk without directly changing the crown's
recursive branch lengths. Decreasing it brings the crown closer to the base.

### `trunk_segments`

Sets how many connected cylinders approximate the trunk. The overall trunk
height remains `trunk_height`.

- More segments create shorter pieces and a smoother stepped taper.
- Fewer segments make each piece longer and the taper coarser.

The code also gives the trunk a fixed, subtle sinusoidal displacement in `x`
and `z`. More segments sample this built-in variation more smoothly; this
variation does not currently have its own configuration control.

### `base_radius`

Sets the trunk radius at its local base. The current trunk begins at `8.0`.

This affects the trunk only. It does not automatically enlarge the recursive
crown, because the top of the trunk and initial leaders use `crown_radius`.

### `crown_radius`

Has two related roles:

1. It is the trunk radius at the top of the clear trunk.
2. It is the base radius supplied to the initial crown leaders, scaled by each
   leader's built-in vigor.

Increasing it can create more structural generations before the branches reach
`min_radius`, so it can increase both crown complexity and terminal crownlet
count. It should normally remain smaller than `base_radius` if the trunk is to
taper upward.

The trunk interpolates linearly from `base_radius` to `crown_radius`.

## Initial crown leaders

### `initial_length`

Sets the reference length of each initial crown leader. The leaders multiply it
by built-in vigor values, so they are deliberately unequal.

The current code creates three leaders with hard-coded `(azimuth, vigor)` pairs:

```text
(18 degrees, 0.98)
(143 degrees, 0.88)
(258 degrees, 0.80)
```

Their initial direction also has a built-in upward component. Consequently,
`initial_length` scales all three leaders, but their number, starting azimuths,
elevations, and vigor values are not yet configurable.

Increasing `initial_length` expands the major scaffold before recursive length
ratios take effect. It can therefore change the crown size dramatically without
adding another generation.

## Structural radius hierarchy

### `alpha`

Controls radius conservation at every structural fork:

```text
r_dominant^alpha + r_lateral^alpha = r_parent^alpha
```

The current value is `2.2`. A random child-radius ratio is first selected from
`asymmetry_min` through `asymmetry_max`; the two child radii are then solved so
that the equation remains true.

For a fixed parent radius and child-radius ratio:

- increasing `alpha` gives the children larger radii relative to the parent;
- decreasing `alpha` makes child radii contract more strongly.

Because `min_radius` terminates structural recursion, `alpha` also influences
how many generations survive and how many crownlets are ultimately produced.

### `min_radius`

Provides the main physical stopping condition for structural recursion.

When the current structural radius is less than or equal to this value, the
generator writes one final structural/foliage segment and attaches a crownlet
at its endpoint.

- Lower values permit more structural generations, many more endpoints, and a
  potentially much denser crown.
- Higher values stop the scaffold earlier, leaving fewer and coarser terminal
  systems.

This parameter can have an exponential effect because every surviving branch
can bifurcate again.

### `max_depth`

Provides a second, safety-oriented stopping condition. Structural recursion
ends if its depth reaches this value even when its radius remains greater than
`min_radius`.

Ideally, `min_radius` is the normal stopping condition and `max_depth` prevents
pathological configurations from producing unbounded geometry. If changing
`max_depth` has no visible effect, the branches are already terminating by
radius.

## Structural branch lengths

### `dominant_length_ratio`

Multiplies the parent length to obtain the stronger child's length before
random jitter:

```text
L_dominant = L_parent * dominant_length_ratio * jitter
```

The current value `0.76` makes the continuation retain more reach than the
lateral child. Raising it creates longer persistent axes; lowering it makes
dominant paths contract faster.

### `lateral_length_ratio`

Multiplies the parent length to obtain the weaker lateral child's length before
random jitter. The current value is `0.62`.

The difference between the dominant and lateral ratios establishes visible
hierarchy. Bringing them closer together produces a more symmetric fractal;
separating them creates stronger primary paths with shorter side branches.

## Structural branch directions

### `dominant_angle`

Sets the nominal turn, in degrees, between a parent and its dominant child.
The current `24.0` supports recognizable continuation through a fork.

- Smaller values produce straighter dominant axes.
- Larger values create a more angular or wandering scaffold.

`angle_jitter` is added independently at every fork, and `upward_bias` is then
added before the direction is normalized.

### `lateral_angle`

Sets the nominal turn between a parent and its lateral child. The current
`48.0` makes lateral branches separate more strongly than dominant branches.

Increasing it opens the structural crown. Decreasing it aligns laterals more
closely with their parents and can produce bundled growth.

### `upward_bias`

Adds a positive amount to the world-space `y` component of every newly tilted
structural or crownlet direction before normalization.

It is not an angle or a percentage. Its visual effect depends on the direction
being modified:

- higher values cause both scaffold branches and crownlet shoots to seek upward
  more aggressively;
- `0.0` removes this explicit upward impetus;
- negative values would bias new directions downward.

Because crownlets use the same direction helper, this one control affects both
large and fine branching.

## Structural variation

### `angle_jitter`

Sets the maximum random angular variation, in degrees, applied independently to
the dominant and lateral angles. The implemented range is approximately
`-angle_jitter` through `+angle_jitter`.

Increasing it makes the scaffold less regular but can introduce strained or
chaotic forks. Setting it to `0.0` exposes the underlying deterministic
recursive pattern.

### `length_jitter`

Sets proportional random variation around each calculated structural child
length. With `0.10`, the multiplier is approximately `0.90` through `1.10`.

- `0.0` makes length scaling exact.
- `0.25` would permit approximately plus or minus 25 percent variation.

This setting applies to structural recursion, not to crownlet internodes, which
have their own fixed built-in variation ranges.

### `asymmetry_min`

Sets the minimum possible ratio between the larger and smaller child radii at a
structural fork. A value of `1.0` permits an equal bifurcation.

The current `1.05` allows nearly balanced forks.

### `asymmetry_max`

Sets the maximum possible ratio between the larger and smaller child radii.
The current maximum is `1.55`.

Increasing it permits a child to dominate more strongly, which makes major
paths more legible and side branches weaker. If the range is too high, many
laterals may terminate quickly at `min_radius`. Both asymmetry limits affect
radius allocation, not branch length directly.

`asymmetry_min` should be positive and should not exceed `asymmetry_max`.

## Leaf controls

### `leaves_enabled`

Controls leaf creation without removing the fine crownlet shoots.

- `true`: add leaves to every final crownlet tip.
- `false`: render the complete woody and fine-twig hierarchy without leaves.

### `leaf_length`

Sets the distance from a leaf's attachment point to its tip. The current value
is `2.8`.

Increasing it enlarges individual leaves and fills visual gaps without adding
new attachment points. It can also conceal fine twigs if taken too far.

### `leaf_width`

Sets the maximum half-width of the lanceolate leaf mesh. Therefore the current
`0.72` produces a maximum full width of approximately `1.44`.

Leaf length and width are independent, allowing narrow or broad forms. The
present leaf is a simple six-vertex, four-triangle mesh and has no configured
curl, vein, serration, or thickness.

Leaves are arranged around a terminal direction with deterministic angular
jitter and a small built-in upward component. Those orientation constants are
not yet configurable.

## Crownlet controls

Crownlets are fine recursive twig systems inserted between every structural
endpoint and its leaves. They are responsible for much of the crown's visible
fullness and maturity.

### `crownlet.style`

Selects the crownlet branching pattern.

- `"open"`: recursively changes branch phase to spread shoots through three
  dimensions.
- `"clustered"`: starts with the open pattern but multiplies its spread and
  child length by the two `clustered_*` controls.
- `"fan"`: holds the recursive phase fixed, producing more directionally
  aligned, flatter terminal systems.

Only these three names are accepted. The current style is `"open"`, so the
clustered multipliers have no effect.

### `crownlet.depth`

Sets the number of recursive crownlet bifurcations. Every shoot produces two
children until the configured depth is reached.

Approximate terminal-tip counts per structural endpoint are:

```text
depth 3 -> 8 tips
depth 4 -> 16 tips
depth 5 -> 32 tips
```

The implementation includes a root crownlet segment at depth zero, so total
crownlet segments per endpoint are approximately `2^(depth + 1) - 1`.

Increasing depth has an exponential effect on twig count, leaf count, scene
size, and render cost.

### `crownlet.length`

Sets the reference length of the first crownlet shoot attached to a structural
endpoint. The actual root length receives a built-in random multiplier from
approximately `0.82` through `1.12`.

The current `10.8` gives the terminal systems substantial reach. Increasing it
enlarges each foliage mass and promotes overlap without lengthening the major
scaffold itself.

### `crownlet.length_ratio`

Sets the base ratio between successive crownlet generations:

```text
L_child = L_parent * length_ratio * built-in variation
```

The first child uses an additional multiplier of approximately `0.90` through
`1.08`; the second uses approximately `0.82` through `1.02`.

Ignoring those variations, the current `length: 10.8` and
`length_ratio: 0.75` give:

```text
generation 0: 10.800
generation 1:  8.100
generation 2:  6.075
generation 3:  4.556
generation 4:  3.417
```

Small ratio changes accumulate over every generation.

### `crownlet.angle`

Sets the nominal divergence angle in degrees. The implemented spread contracts
by 10 percent of the base angle for each deeper generation:

```text
spread_at_depth = angle * (1 - 0.10 * depth)
```

The second child uses 112 percent of that generation's spread. Both children
also receive a small built-in phase jitter.

- Larger angles make broad, spatially distributed crownlets.
- Smaller angles make elongated brushes or bundles.

The current `40.0` is moderately open.

### `crownlet.radius_ratio`

Directly scales fine-shoot radius at every crownlet generation:

```text
r_child = max(r_parent * radius_ratio, 0.035)
```

The second child begins its next recursive call at an additional factor of
`0.88`, although the segment leading to it shares the initially calculated tip
radius. The hard minimum radius is `0.035`.

This ratio does not use the structural `alpha` conservation equation, and it
does not terminate crownlet recursion; `crownlet.depth` does that.

### `crownlet.clustered_spread_ratio`

Used only for the `"clustered"` style. It multiplies the ordinary angle at every
generation.

With `angle: 40.0` and `clustered_spread_ratio: 0.30`, the first clustered
spread is:

```text
40 degrees * 0.30 = 12 degrees
```

It has no effect when style is `"open"` or `"fan"`.

### `crownlet.clustered_length_ratio`

Also used only for `"clustered"`. It multiplies the child length after the
ordinary `crownlet.length_ratio` is applied.

With the current values, the effective base multiplier is:

```text
0.75 * 0.62 = 0.465
```

Ignoring built-in variation, lengths contract approximately as follows:

```text
generation 0: 10.800
generation 1:  5.022
generation 2:  2.335
generation 3:  1.086
generation 4:  0.505
```

It has no effect when style is `"open"` or `"fan"`.

### `crownlet.leaves_per_tip`

Sets how many leaves are placed around each final crownlet tip.

At `depth: 4`, there are approximately 16 tips per crownlet, so the current
value produces approximately:

```text
16 tips * 8 leaves = 128 leaves per structural endpoint
```

This is a direct foliage-density multiplier, but it creates no new twigs and
does not increase crownlet reach.

- Increase `depth` to create more twig structure and distribute more tips.
- Increase `leaves_per_tip` to pack more leaves onto existing tips.
- Increase `length`, `length_ratio`, or `angle` to distribute those tips across
  more space.

## Materials

### `wood_reflectance`

Sets linear RGB diffuse reflectance for trunk and structural wood. The current
value is `[0.20, 0.085, 0.020]`.

It changes surface response, not geometry. Values should generally remain in
the `0.0` through `1.0` range.

### `foliage_reflectance`

Sets linear RGB diffuse reflectance for fine crownlet shoots and leaves. The
current value is `[0.020, 0.18, 0.035]`.

Fine shoots are intentionally assigned the foliage material even though they
are geometric branch segments. A future material split could give twigs and
leaves independent colors.

## Important interactions

### Structural complexity

The strongest interacting controls are:

```text
crown_radius + alpha + asymmetry range + min_radius + max_depth
```

Together they determine how many structural branches survive and how many
crownlet attachment points exist.

### Crown fullness

Fullness is not equivalent to leaf count. It is produced jointly by:

```text
number of structural endpoints
* crownlet terminal tips per endpoint
* leaves per tip
* spatial reach of the crownlets
```

Thus:

- `crownlet.depth` creates exponentially more fine structure;
- `crownlet.leaves_per_tip` thickens existing terminal clusters;
- `crownlet.length`, `length_ratio`, and `angle` distribute foliage through
  space;
- `min_radius` changes how many structural endpoints receive crownlets.

### Silhouette versus internal visibility

- Greater depth, reach, spread, and leaves per tip build a continuous canopy.
- Lower values preserve openings through which the scaffold remains visible.
- Larger leaves fill gaps quickly but can conceal fine branching without adding
  structural richness.

### Computational cost

Both structural recursion and crownlet recursion bifurcate. Increasing either
`max_depth`/lowering `min_radius`, or increasing `crownlet.depth`, can therefore
multiply geometry rather than merely add to it. Before making several such
changes together, test one generation increase and inspect the reported segment
and leaf counts.

## Current non-configurable behavior

The following remain hard-coded in `fractal_tree.py` and are candidates for
future modular controls:

- the number, azimuth, elevation, and vigor of initial crown leaders;
- the trunk's sinusoidal displacement;
- structural phase rotations of `+137.5` and `-99.5` degrees;
- crownlet child-length variation ranges;
- crownlet phase jitter;
- leaf orientation, upward bias, and angular jitter;
- leaf mesh shape;
- the crownlet minimum radius of `0.035`;
- separate materials for fine twigs and leaves.

Keeping this boundary explicit helps distinguish genuine configuration controls
from behavior that currently requires a code change.
