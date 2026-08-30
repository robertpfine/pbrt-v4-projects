# Grass configuration

Grass controls live under `scene.landscape.ground.details.grass` in
`config.json`.
Values in `blade` and `tuft` define each reusable tuft mesh. The layer's
`scale` is applied afterward to every dimension of each instance.

Named configurations discovered during render experiments are preserved in
`grass_presets.json`. Copy a preset's `blade` object over the grass `blade`
object in `config.json` to reproduce it.

## Blade controls

- `height`: Minimum and maximum blade length in scene units.
- `width`: Minimum and maximum half-width at the base of a blade.
- `segments`: Number of lengthwise sections. Use 6–10 for tall curved grass.
- `lean`: Minimum and maximum horizontal displacement of the blade tip.
- `lean_spread_degrees`: Variation between the blade's facing direction and
  its leaning direction.
- `bend`: Signed sideways bow at the middle of the blade. A range crossing
  zero bends blades in both directions.
- `bend_exponent`: Controls where the lean develops. Larger values keep the
  base straighter and concentrate the curve toward the tip.
- `tip_droop`: Amount subtracted from blade height toward the tip. Keep its
  maximum below the minimum `height`.
- `tropism.enabled`: Enables a shared directional influence across the sward.
- `tropism.direction_degrees`: Prevailing direction of that influence around
  the terrain's vertical axis.
- `tropism.strength`: Minimum and maximum sideways displacement caused by the
  influence. This varies between blades.
- `tropism.direction_variation_degrees`: Per-blade angular variation around
  the prevailing direction.
- `tropism.curvature_exponent`: Larger values preserve a straighter base and
  concentrate the directional response toward the blade tip.
- `tropism.field.frequency`: Spatial frequency of broad directional currents
  across the terrain. Smaller values make larger swaths.
- `tropism.field.direction_variation_degrees`: Maximum swing of those currents
  around the prevailing tropism direction.
- `tropism.field.octaves` and `persistence`: Complexity of the smooth direction
  field. One octave is broad and simple; additional octaves add nested movement.
- `tropism.field.random_jitter_degrees`: Small uncorrelated rotation added to
  individual tufts after the smooth field is evaluated.
- `taper_exponent`: Controls how quickly the blade narrows toward its tip.

## Tuft controls

- `blades`: Number of blades in each tuft.
- `radius`: Minimum and maximum distance of blade bases from the tuft center.
- `angle_jitter_degrees`: Random variation in blade direction.

## Placement controls

- `layers[].count`: Number of tuft instances.
- `layers[].scale`: Random overall scale multiplier. It affects height, width,
  radius, lean, bend, and droop together.
- `layers[].patchiness.strength`: Zero is even coverage; larger values make
  open and dense patches.
- `layers[].patchiness.frequency`: Spatial frequency of those patches.
- `region`: Center and size of the scatter area.
- `max_slope_degrees`: Steepest terrain that accepts grass.
- `exclusion`: Grass-free circle, currently used around the tree trunk.

## Starting point for tall bending grass

```json
"blade": {
  "height": [4.0, 7.0],
  "width": [0.035, 0.075],
  "segments": 7,
  "lean": [0.15, 0.55],
  "lean_spread_degrees": 35.0,
  "bend": [-1.4, 1.4],
  "bend_exponent": 2.0,
  "tip_droop": [0.0, 0.8],
  "tropism": {
    "enabled": true,
    "direction_degrees": 45.0,
    "strength": [1.0, 4.0],
    "direction_variation_degrees": 45.0,
    "curvature_exponent": 2.0
  },
  "taper_exponent": 1.35
},
"tuft": {
  "blades": 7,
  "radius": [0.03, 0.18],
  "angle_jitter_degrees": 18.0
}
```

For predictable length experiments, first set `layers[].scale` to `[1.0, 1.0]`.
Once the basic length and curvature look right, widen that range to restore
natural variation. Increasing `segments` changes the shared tuft mesh, so it is
far less expensive than increasing `layers[].count` by the same factor.
