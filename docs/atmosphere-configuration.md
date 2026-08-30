# Atmosphere Configuration Guide

The current atmosphere system provides a finite homogeneous fog medium for
PBRT-v4. It is configured under `scene.fog` and written by
[`scene_workspace/build_scene.py`](../scene_workspace/build_scene.py).

```json
"fog": {
  "enabled": true,
  "sigma_a": 0.00002,
  "sigma_s": 0.00075,
  "g": 0.65,
  "camera_inside": true,
  "boundary_center": [0.0, 100.0, 0.0],
  "boundary_radius": 700.0,
  "noise": {
    "enabled": true,
    "type": "perlin",
    "seed": 19,
    "resolution": [48, 36, 48],
    "bounds_min": [-700.0, -500.0, -700.0],
    "bounds_max": [700.0, 700.0, 700.0],
    "frequency": 0.006,
    "octaves": 3,
    "persistence": 0.50,
    "lacunarity": 2.0,
    "base_density": 0.55,
    "contrast": 1.20
  }
}
```

## Controls

### `enabled`

Declares and activates the fog medium when `true`. When `false`, the scene is
rendered in vacuum.

### `sigma_a`

Sets homogeneous absorption per world unit. Absorption removes radiance rather
than redirecting it. Larger values darken long paths through the atmosphere.

The current `0.00002` introduces only slight absorption so that scattering,
rather than extinction to black, dominates the morning-fog appearance.

### `sigma_s`

Sets homogeneous scattering per world unit. Larger values produce denser fog,
more veiling, stronger light bloom, and less distant contrast.

The approximate scattering optical thickness over distance `d` is:

```text
tau_s = sigma_s * d
```

At `sigma_s: 0.00075`, a 500-unit path has `tau_s = 0.375` before absorption is
included. Perceived density also depends strongly on lighting and phase
anisotropy.

### `g`

Sets the Henyey-Greenstein phase-function asymmetry:

- `0.0`: isotropic scattering;
- positive values: preferential forward scattering;
- negative values: preferential backward scattering;
- values must remain between `-1` and `1`.

The current `0.65` favors forward scattering, which allows low sunlight to
bloom through the fog. Values closer to `1` can create stronger directional
glow but may increase variance and render noise.

### `camera_inside`

When `true`, the camera begins inside the named `fog` medium. This must agree
with the camera's actual relationship to the finite boundary.

The current test places the camera inside the boundary sphere. Setting this to
`false` while leaving the camera physically inside would give PBRT an
inconsistent starting medium.

### `boundary_center`

Sets the world-space center of the invisible spherical atmosphere boundary.
The current `[0,100,0]` centers the volume vertically around the terrain, tree,
and elevated camera.

### `boundary_radius`

Sets the fog sphere's radius. The boundary uses PBRT's `interface` material, so
it is invisible but provides a transition from fog inside to vacuum outside.

The sphere must contain every point intended to lie in fog, including the
camera when `camera_inside` is true. Making it unnecessarily large increases
atmospheric path lengths and can produce excessive veiling.

## Why the boundary is required

An unbounded homogeneous camera medium gives background rays no finite exit
distance. With scattering illumination, that can wash the image completely to
white. The explicit sphere gives rays a well-defined transition back to vacuum
and makes density controllable.

## Perlin density variation

When `fog.noise.enabled` is `true`, the homogeneous medium is replaced by a
PBRT-v4 `uniformgrid` medium. The configured 3D Perlin field supplies a density
multiplier at every voxel; `sigma_a`, `sigma_s`, and `g` retain their ordinary
physical roles.

### `noise.type`

Documents the intended procedural field. The implemented value is `"perlin"`.

### `noise.seed`

Selects a reproducible arrangement of dense and thin regions without changing
their scale or contrast.

### `noise.resolution`

Sets `[nx,ny,nz]` samples in the PBRT uniform grid. The current `[48,36,48]`
contains 82,944 density samples. Larger grids preserve finer variation but
increase scene size, memory use, startup time, and potentially render cost.

### `noise.bounds_min` and `noise.bounds_max`

Define the world-space box mapped by the density grid. It should contain the
camera and visible atmosphere while remaining compatible with the finite
boundary. Density outside this box is not represented by the grid.

### `noise.frequency`

Sets Perlin cycles per world unit. The approximate first-octave feature scale at
`0.006` is `1 / 0.006`, or about 167 world units. Lower values produce broader
mist banks; higher values produce smaller mottling.

### `noise.octaves`, `noise.persistence`, and `noise.lacunarity`

Control fractional Brownian accumulation within the Perlin call:

- `octaves` sets the number of scales;
- `persistence` reduces amplitude between scales;
- `lacunarity` increases frequency between scales.

### `noise.base_density`

Sets the density multiplier around which Perlin variation occurs. Lowering it
creates more transparent gaps. Raising it preserves a continuous fog blanket.

### `noise.contrast`

Multiplies the signed Perlin value before it is added to `base_density`:

```text
density = max(0, base_density + contrast * perlin)
```

Higher contrast produces stronger separation between clear and dense regions.
Values that drive the expression below zero create genuinely empty voxels.

## Lighting interaction

Fog appearance cannot be judged from density alone. Important interacting
controls are:

- distant-light direction and intensity;
- light color or blackbody temperature;
- ambient infinite-light intensity;
- `sigma_s` and `sigma_a`;
- phase asymmetry `g`;
- camera-to-subject distance and boundary size.

The current morning test uses a 4600 K low directional light. Warmer light is
therefore a lighting choice, not an intrinsic color assigned to the fog.

## Performance and noise

Participating media add scattering events to camera, shadow, and indirect-light
paths. They can substantially increase render time and variance. Forward
scattering, dense foliage, high path depth, and bright directional lighting are
especially demanding together.

If an image is attractively composed but noisy, increase pixel samples before
changing the atmosphere solely to suppress variance. For exploratory renders,
lower resolution or reduced foliage can provide faster feedback.

## Current limitations

- Perlin variation is available, but there is no finite-height ground-fog
  falloff yet.
- There is no vertical density falloff.
- There is no procedural density noise or drifting mist structure.
- Fog color is neutral; color comes from incident illumination and absorption.
- The boundary is spherical rather than terrain-following.
- Clouds are not part of this system.

Future atmosphere modes should preserve a finite boundary while adding height
falloff, bounded fog layers, and heterogeneous density fields.
