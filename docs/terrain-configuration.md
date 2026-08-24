# Terrain Configuration Guide

Procedural terrain is implemented in [`terrain.py`](../terrain.py), written to
PBRT by [`rgbgrid-medium/build_scene.py`](../rgbgrid-medium/build_scene.py), and
configured under `scene.terrain`.

The first supported terrain type is `rolling_hillside`. It combines a planar
incline with deterministic, smooth, multi-octave value noise:

```text
y(x,z) = base_height
       + grade * (x cos(theta) + z sin(theta))
       + sum(amplitude * persistence^i
             * noise(frequency * lacunarity^i * x,
                     frequency * lacunarity^i * z))
```

## Complete example

```json
"terrain": {
  "enabled": true,
  "type": "rolling_hillside",
  "size": [1200.0, 1200.0],
  "resolution": [257, 257],
  "base_height": 0.0,
  "slope": {
    "direction_degrees": 320.0,
    "grade": 0.40,
    "foreground_leveling": {
      "enabled": true,
      "direction_degrees": 51.5,
      "start": 0.0,
      "end": 180.0,
      "minimum_grade_ratio": 0.0,
      "target_height": 0.0
    }
  },
  "noise": {
    "seed": 7,
    "amplitude": 14.0,
    "frequency": 0.008,
    "octaves": 3,
    "persistence": 0.45,
    "lacunarity": 2.0
  },
  "material": {
    "reflectance": [0.10, 0.17, 0.045]
  }
}
```

## General controls

### `enabled`

Creates and renders the terrain when `true`. When `false`, no terrain mesh is
written and terrain-aware object placement is not applied.

### `type`

Selects the terrain algorithm. The only currently supported value is
`"rolling_hillside"`. Future terrain types can implement the same `height()`,
`sample()`, and `mesh()` interface.

### `size`

The `[width, depth]` of the generated mesh in world units. It is centered on
local `(x,z) = (0,0)` and therefore extends half the width and depth in both
directions.

This setting changes the terrain's coverage, not the scale of its noise. A
larger mesh with unchanged frequency reveals more repetitions of the same
landform scale.

### `resolution`

The `[x_vertices, z_vertices]` grid resolution. A value of `[129,129]` creates
16,641 vertices and 32,768 triangles.

- Higher resolution represents smaller terrain features and smoother normals
  more accurately.
- Lower resolution is faster and can give the surface an intentionally faceted
  character.
- Each component must be at least `2`.

Geometry and scene-file size grow approximately with the product of the two
values. Doubling both dimensions creates roughly four times as many vertices
and triangles.

### `base_height`

Adds a constant world-space vertical offset to the complete terrain. It does
not change slope or relief.

## Slope controls

### `slope.direction_degrees`

Sets the horizontal direction in which the planar component rises:

```text
0 degrees   -> rising toward +X
90 degrees  -> rising toward +Z
180 degrees -> rising toward -X
270 degrees -> rising toward -Z
```

The current `25.0` makes elevation rise through a combination of `+X` and `+Z`.

### `slope.grade`

Sets rise divided by horizontal run along the configured direction. It is not
an angle. A grade of `0.18` rises 18 units for every 100 horizontal units before
noise is added.

The equivalent planar angle is:

```text
atan(0.18) = approximately 10.2 degrees
```

Negative grades reverse the incline. A value of `0.0` removes the overall
hillside but preserves rolling noise.

### `slope.foreground_leveling`

Optionally turns the constant hillside into a graded landform that levels out
toward a chosen horizontal direction. The transition affects the planar slope;
the rolling noise remains present across the foreground.

- `enabled` activates the transition.
- `direction_degrees` points toward the foreground, using the same world-axis
  convention as `slope.direction_degrees`. For the current camera, `51.5`
  points approximately from the tree toward the camera.
- `start` is the projected distance at which flattening begins. Negative and
  smaller coordinates retain the original hillside grade.
- `end` is the distance at which the transition reaches its minimum grade.
- `minimum_grade_ratio` is the fraction of the original grade retained beyond
  `end`. The current `0.0` produces a level foreground in the chosen direction.
- `target_height`, when present, is the planar elevation toward which the
  foreground converges. The current `0.0` removes the hillside's cross-frame
  incline as well as its camera-facing incline. When omitted, leveling only
  removes grade along `direction_degrees` and preserves perpendicular slope.

The blend uses a smoothstep curve, so neither end of the transition introduces
a hard crease. The configured noise field remains visible at full strength.

## Noise controls

### `noise.seed`

Selects a deterministic value-noise field. Identical terrain parameters and
seed reproduce identical heights. Changing it creates a different arrangement
of rises and depressions without changing their statistical scale.

### `noise.amplitude`

Sets the maximum coefficient of the first and largest noise octave. Later
octaves are scaled by `persistence`.

Increasing amplitude creates greater vertical relief. It also increases local
slope and may require higher mesh resolution. Setting it to `0.0` leaves only
the planar incline.

### `noise.frequency`

Sets the first octave's cycles per world unit. Approximate feature scale is the
inverse:

```text
1 / 0.008 = 125 world units
```

- Lower frequency produces broader landforms.
- Higher frequency produces smaller, more frequent undulations.

For fields where trees remain the subject, low frequency is usually preferable.

### `noise.octaves`

Sets how many noise scales are summed. Each octave increases frequency by
`lacunarity` and decreases amplitude by `persistence`.

- One octave gives only the broadest rolls.
- Two to four octaves add progressively smaller variation.
- Many octaves can create visually busy terrain and may exceed the mesh's
  ability to represent the smallest features.

It must be at least `1`.

### `noise.persistence`

Multiplies amplitude between octaves. At `0.45`, the octave amplitudes beginning
with `14.0` are approximately:

```text
14.000, 6.300, 2.835
```

Higher values preserve more small-scale relief and roughness. Lower values make
the broad landform dominate.

### `noise.lacunarity`

Multiplies frequency between octaves. At `2.0`, frequencies beginning with
`0.008` are:

```text
0.008, 0.016, 0.032
```

Higher values separate the scales more aggressively. Values near `2.0` are a
useful starting point.

## Material

### `material.reflectance`

Sets the terrain's linear RGB diffuse reflectance. It affects appearance only,
not height, normals, or placement.

The initial `[0.10, 0.17, 0.045]` is a subdued green suitable for testing tree
contact and landform lighting without adding grass geometry.

## Sampling and normals

`RollingHillside.sample(x,z)` returns:

- `height`: terrain height at the requested horizontal position;
- `normal`: normalized world-space surface normal;
- `slope_degrees`: local slope angle measured from horizontal.

Normals and slopes are calculated from central finite differences of the same
continuous height function used to generate the mesh. The mesh writes a normal
at every vertex for smooth PBRT shading.

## Placing a fractal tree on terrain

The tree retains its own `origin` for horizontal placement and adds a placement
block:

```json
"origin": [0.0, 0.0, 0.0],
"terrain_placement": {
  "enabled": true,
  "height_offset": 0.0
}
```

When enabled, the scene builder samples terrain at `origin[0]` and `origin[2]`
and replaces the tree's vertical origin with:

```text
terrain height + height_offset
```

The generated trunk continues to grow in world `+Y`; it is not rotated to the
surface normal. This makes trees stand upright relative to gravity on slopes.

`height_offset` can correct deliberate embedding or clearance. A positive value
lifts the root; a negative value embeds it.

## Current limitations

- Only `rolling_hillside` is implemented.
- Terrain is centered at the world origin and has no independent transform.
- The mesh is a regular rectangular grid without adaptive subdivision.
- There is no erosion, drainage, ridge, terrace, or general boundary-falloff
  model. Directional foreground leveling is supported for the planar slope.
- Value noise is deterministic but is not gradient Perlin or simplex noise.
- Terrain-aware placement currently applies to configured L-system/fractal-tree
  entries, not yet to groves or space-colonization tree instances.
- Terrain material is diffuse and has no grass, texture map, displacement, or
  soil/rock blending.
- Sampling outside the displayed mesh remains mathematically defined, but an
  object placed there would have no visible ground underneath it.

These constraints keep the first terrain slice understandable while preserving
a common interface for rolling fields, mountains, water placement, and
terrain-aware vegetation distributions.
