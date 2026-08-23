# Lighting Configuration Guide

Scene lights are configured in the `scene.lights` array and written to PBRT-v4
by [`rgbgrid-medium/build_scene.py`](../rgbgrid-medium/build_scene.py). Multiple
enabled lights contribute simultaneously.

## Parallel sunlight aperture

The current shaft experiment uses a PBRT `distant` light and an opaque mask
placed perpendicular to its direction. A seeded Perlin pattern perforates the
mask, producing multiple delicate bundles of parallel rays.

```json
"sun_aperture": {
  "enabled": true,
  "light": "shaft_sun",
  "mode": "cloud_breakup",
  "beam_target": [70.0, 180.0, 20.0],
  "mask_distance": 5000.0,
  "outer_radius": 1100.0,
  "grid_resolution": 128,
  "cloud_frequency": 0.010,
  "cloud_octaves": 2,
  "open_threshold": 0.16,
  "seed": 31,
  "reflectance": [0.001, 0.001, 0.001]
}
```

`light` names an enabled, labeled `distant` light. `beam_target` is a point on
the desired beam axis. `mask_distance` places the mask upstream from that point
along the solar direction. Neither setting changes ray direction.

`mode: "cloud_breakup"` tessellates the mask and removes cells selected by a
two-dimensional Perlin field. `grid_resolution` controls edge detail,
`cloud_frequency` controls the typical opening size, and `cloud_octaves`
controls boundary complexity. Cells whose noise exceeds `open_threshold` are
open; increasing the threshold makes openings fewer and smaller. `seed`
selects a deterministic breakup pattern. `outer_radius` must cover every solar
ray that could otherwise reach the visible scene.

The mask is deliberately almost black and positioned far outside the camera
view. The long mask distance does not make the light diverge: the distant-light
rays remain parallel at every distance.

The current scene deliberately uses two distant lights. `morning_sun` retains
the original `from: [-16, 5, 9]` direction, approximately 15 degrees above the
horizon, and illuminates the complete Perlin atmosphere. `shaft_sun` uses
`from: [-5, 16, -25]`, approximately 32 degrees above the horizon, and is the
only light targeted by the aperture configuration. This direction sends the
descending beam generally toward the camera, making the fog's forward
scattering visible. Both lights have parallel rays; the separation preserves
the original ambient scene while adding an independently controllable
higher-angle shafts. The current shaft scale is `12`, only modestly stronger
than the base sun's scale of `9`, so the shafts remain delicate rather than
bright white.
The spotlight remains in the configuration as a disabled comparison.

## Rejected spotlight experiment

The first shaft experiment used:

```json
{
  "enabled": true,
  "type": "spot",
  "position": [180, 340, -260],
  "look_at": [135, 20, 190],
  "cone_angle": 12,
  "cone_delta_angle": 5,
  "color_mode": "blackbody",
  "temperature": 4400,
  "scale": 220000.0
}
```

This was an artistic approximation of a confined sunbeam. The source was placed
on the far, image-right side of the tree and directed generally toward the
camera so that the forward-scattering atmosphere reveals its path. Its axis
grazes the right crown rather than striking the tree directly. A real solar shaft
would contain nearly parallel rays produced by a distant source passing through
an aperture or occluding cloud. A PBRT spotlight instead emits a cone from a
finite point, but it is efficient and highly controllable for composition.

### `enabled`

Adds the light when `true`. Disabling it preserves all settings for comparison.

### `type`

Must be `"spot"` for this light. The scene builder also supports `infinite`,
`point`, and `distant` lights.

### `position`

Sets the world-space source point. The current source is high and to the side of
the camera, inside the finite fog boundary.

The position affects both beam direction and geometric divergence. Moving the
source farther away makes rays within the visible scene more nearly parallel,
but requires a larger atmosphere boundary if the source must remain inside it.

### `look_at`

Sets the world-space target at the center of the cone. The current target lies
near the ground to the left of the trunk, directing the shaft diagonally through
the crown.

### `cone_angle`

Sets the full outer cone angle in degrees. Smaller values produce a narrower,
more concentrated shaft. Larger values illuminate more of the scene and can
read as general fill rather than a distinct beam.

### `cone_delta_angle`

Sets the angular width of the transition from full intensity to zero at the
cone boundary. A value of `0` gives a hard edge. Larger values soften the beam
boundary.

This value should normally be smaller than `cone_angle`.

### `color_mode`

Selects how spectrum is specified:

- `"blackbody"` uses `temperature` in Kelvin;
- `"rgb"` uses a three-component `color` array.

### `temperature`

Sets blackbody color temperature when `color_mode` is `"blackbody"`. The
current 4400 K is warmer than neutral midday daylight and supports a morning
appearance.

### `scale`

Multiplies spotlight intensity. Point and spot lights undergo inverse-square
falloff, so their useful scale depends strongly on source distance. The large
current value is a deliberate bookend for a source hundreds of world units from
the subject.

## Interaction with atmosphere

A light shaft is visible only when light scatters toward the camera. Its
appearance depends on:

- fog `sigma_s`;
- heterogeneous density along the cone;
- phase asymmetry `g`;
- light direction relative to the camera;
- cone angle and transition;
- source intensity and distance;
- sample count.

Perlin fog can interrupt or modulate the shaft, producing broken bright and dim
regions rather than a uniform cone.

## Supporting lights in the current test

The ambient infinite light is reduced to `scale: 0.035`, and the broad distant
sun is reduced to `scale: 4.0`. They retain environmental visibility while
allowing the spotlight shaft to become the dominant event.

## Current limitations

- The spotlight is not physically parallel sunlight.
- There is no cloud or aperture geometry casting the shaft.
- Beam placement is specified directly in world coordinates.
- There is no named lighting preset or dedicated `sun_shaft` configuration yet.
- Volumetric shafts can be noisy and expensive at exploratory sample counts.
