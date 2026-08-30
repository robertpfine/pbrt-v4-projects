# Terrain Configuration Guide

Procedural terrain is implemented in [`terrain.py`](../terrain.py), written to
PBRT by [`scene_workspace/build_scene.py`](../scene_workspace/build_scene.py), and
configured under `scene.terrain`. One authoritative JSON contains named
landform profiles plus shared material and ecosystem-detail controls.

Each named landform currently uses the `RollingHillside` implementation. It
combines a planar incline with deterministic, smooth, multi-octave value noise:

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
  "active_landform": "flat_landform",
  "landforms": {
    "flat_landform": {
      "size": [1200.0, 1200.0],
      "resolution": [257, 257],
      "base_height": 0.0,
      "slope": {
        "direction_degrees": 270.0,
        "grade": 0.025,
        "foreground_leveling": { "enabled": false }
      },
      "noise": {
        "seed": 113,
        "amplitude": 5.5,
        "frequency": 0.0045,
        "octaves": 4,
        "persistence": 0.48,
        "lacunarity": 2.0
      }
    }
  },
  "material": {
    "reflectance": [0.10, 0.17, 0.045]
  },
  "details": {
    "surface": { "enabled": true },
    "grass": { "enabled": true, "count": 2400 },
    "poppies": { "enabled": true, "count": 120 },
    "litter": { "enabled": true, "count": 950 },
    "rocks": { "enabled": true, "count": 48 },
    "undergrowth": { "enabled": true, "count": 140 }
  }
}
```

## General controls

### `enabled`

Creates and renders the terrain when `true`. When `false`, no terrain mesh is
written and terrain-aware object placement is not applied.

### `active_landform`

Selects exactly one key from `landforms`. Changing it changes ground geometry
without disconnecting or duplicating the shared material, grass, poppies,
litter, rocks, or undergrowth configuration. The legacy top-level `type` layout
remains readable for older configurations, but named landforms are preferred.

### `landforms`

Contains named geometry profiles. `right_dip_rise` preserves the established
gully terrain; `flat_landform` provides a broad, gently rising meadow. These are
configuration profiles of the same terrain implementation, not separate scene
files or separate ecosystem stacks.

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

## Surface and ecosystem details

The optional `terrain.details` system adds one surface treatment plus five
independently switchable instanced layers. All placement is deterministic for a
given seed and samples the actual terrain height, normal, and local slope.

Object layers may also constrain placement to the active camera with a
`camera_frustum` block:

```json
"camera_frustum": {
  "enabled": true,
  "frame_margin": 0.02,
  "bounds_radius": 0.95
}
```

When enabled, candidates are rejected until `count` complete instances fit
inside the camera frustum. `frame_margin` reserves a fraction of each half-frame
at the image edges. `bounds_radius` is the object's conservative local-space
radius; it is multiplied by each instance's randomized scale and aspect so
petals and foliage are not accepted merely because their stem origin is in
frame. This is a framing constraint, not an occlusion test: terrain and other
geometry may still hide an accepted instance.

### `details.surface`

This layer enriches the terrain mesh itself rather than adding objects.

- `enabled` selects procedural color and micro-displacement.
- `dark_reflectance` and `light_reflectance` are the endpoints mixed by a
  broad three-dimensional fBm field.
- `color_frequency` controls the size of soil/vegetation color regions. Lower
  values make broader regions.
- `color_octaves` and `color_roughness` control the complexity and persistence
  of the color field.
- `micro_frequency` controls the scale of fine surface relief.
- `micro_octaves` and `micro_roughness` control its fractal character.
- `micro_amplitude` is the displacement height in world units. Keep it small
  relative to terrain grid spacing; it is surface texture, not a new landform.
- `flow_direction_degrees` rotates directional surface structure around world
  Y. It is useful for grass laid by wind, drainage, mowing, or slope flow.
- `color_anisotropy` stretches broad color variation along the flow direction;
  `micro_anisotropy` independently stretches fine displacement detail.
- `fiber_reflectance` and `fiber_strength` add a restrained fine-scale color
  component over the broad surface color. `fiber_frequency`,
  `fiber_anisotropy`, `fiber_octaves`, and `fiber_roughness` control its scale,
  directionality, and complexity. Together these controls can make distant and
  middle-ground vegetated terrain register as continuous fibrous texture
  without blade geometry.

Set `mode` to `terrain_surface_texture` to use deterministically generated
seamless image maps instead of the generic fBm surface. The terrain mesh
receives UV coordinates, and PBRT uses separate albedo and bump maps. This is
intended for fields viewed at a distance, where grass should register as texture
rather than as thousands of individual blades.

The nested `terrain_surface_texture` controls are:

- `resolution`: width and height of both square texture maps.
- `seed`: repeatable surface pattern.
- `flow_direction_degrees`: dominant lay of the elongated fibers.
- `dark_color` and `light_color`: sRGB endpoints for broad surface variation.
- `fiber_contrast`: visibility of the fine interwoven directional pattern.
- The seamless sward is synthesized from broad growth variation and several
  anisotropic frequency bands: long blades, short blades, and a weaker crossing
  layer. Their built-in scale separation prevents the texture from reading as
  drawn hairs or a single combed noise field.
- `bump_contrast`: contrast encoded in the grayscale bump map.
- `bump_scale`: PBRT displacement strength; keep this small so the map affects
  surface response without changing the hillside silhouette.

### Shared scatter controls

The `grass`, `poppies`, `litter`, `rocks`, and `undergrowth` blocks share these
controls:

- `enabled` activates the layer.
- `count` is the requested number of object instances, not the number of blades
  or leaves inside a reusable cluster.
- `seed` makes placement, rotation, scale, and shape variation repeatable.
- `region.center` is `[x,z]`; `region.size` is its rectangular coverage.
- `scale` is a randomized `[minimum,maximum]` uniform size range.
- `max_slope_degrees` rejects sites steeper than the limit.
- `patchiness.strength` blends between uniform acceptance (`0`) and strong
  noise-controlled colonies (`1`).
- `patchiness.frequency` controls colony size.
- `exclusion.center` and `exclusion.radius` reserve a circular clear area,
  useful at the trunk base.
- `attraction.center`, `attraction.radius`, and `attraction.strength` bias a
  layer toward a circular ecological zone. The current litter layer uses this
  to concentrate debris beneath the crown.
- `y_offset` raises or embeds instances relative to the sampled surface.
- `variants` selects how many reusable material variants are defined.
- `reflectance_variants` supplies their linear RGB diffuse colors.

### Grass

Each grass instance is a small crossed cluster of seven differently leaning
blades. Thousands of clusters can therefore describe a field without emitting
each blade as an independent scene object. The current exclusion radius keeps
the immediate trunk contact readable, while high patchiness creates bare soil
between colonies.

An optional `layers` array creates multiple grass strata from the same reusable
blade cluster. Values in each layer override the shared grass controls. This is
useful for pasture treatments: a high-count, weakly patchy, short base stratum
provides nearly continuous coverage, while a lower-count, taller stratum adds
irregular tufts and seed-stalk-like accents. If `layers` is absent, the original
single-layer grass configuration remains valid.

### Ground litter

Litter instances are shallow folded leaf shapes. They are concentrated in a
smaller region beneath the tree and use several brown reflectances. Increase
`count` for continuity, `scale` for more graphic individual leaves, or the
attraction strength for a more sharply defined accumulation below the crown.

### Rocks

Rocks are non-uniformly scaled and randomly rotated sphere instances. Their
independent axis variation makes ellipsoidal forms, and a negative `y_offset`
partly buries them. The system intentionally uses few rocks so they become
accents rather than a uniformly pebbled surface.

### Undergrowth

The first undergrowth organ is a reusable stylized fern composed of five curved
fronds and paired leaflets. High patchiness forms separate colonies. This block
can later become a general species list without changing the scatter interface.

### Ecological layering

The layers deliberately use different fields and spatial rules:

```text
open slope      -> patchy grasses
beneath crown   -> concentrated leaf litter
exposed regions -> occasional partly buried rocks
moist-looking patches -> fern colonies
```

This avoids the synthetic appearance of distributing every object uniformly
over the full terrain rectangle.

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
- Surface variation and ground-cover layers are procedural but do not yet model
  drainage, moisture transport, plant competition, or true soil/rock blending.
- Grass and fern organs are stylized low-complexity meshes rather than botanical
  species models.
- Sampling outside the displayed mesh remains mathematically defined, but an
  object placed there would have no visible ground underneath it.

These constraints keep the first terrain slice understandable while preserving
a common interface for rolling fields, mountains, water placement, and
terrain-aware vegetation distributions.
