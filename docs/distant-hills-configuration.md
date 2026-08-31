# Distant Hills Configuration

The distant-hill system lives at `scene.landscape.distant_hills` in the one
authoritative `scene_workspace/config.json`. It generates real world-space
triangle meshes with front slopes, designed ridges, and rear slopes.

## Module and layers

`enabled` switches the entire system. `layers` contains independently
editable depth layers. Each layer has its own placement,
silhouette, surface irregularity, and color.

- `center`: world-space `[x, z]` center of the terrain band.
- `size`: band `[width, depth]` before rotation.
- `rotation_degrees`: rotation of the band in the ground plane.
- `resolution`: mesh vertices across the width and depth.
- `base_elevation`: height at the concealed front and rear edges.
- `ridge_base_height`: continuous relief beneath all designed peaks.
- `shading_normal_up_blend`: optional distant-layer lighting softener. Values
  near `1` suppress harsh grazing-angle contrast while retaining the geometric
  silhouette; it is used for strongly atmospheric far ranges, not foreground
  terrain.
- `material.reflectance`: RGB surface reflectance for the layer.

The present composition keeps two prospective hill ranges disabled, uses
`intermediate_field` as the pale horizontal depth interval carrying the tree
line, and places `distant_hills` substantially behind it. The distant hills use
low irregular relief, restrained small-scale noise, and cool blue-gray-green
reflectance to establish atmospheric perspective before scene-wide haze is
introduced. The layers overlap in depth so the base of each distant band is
hidden by the terrain in front of it.

## Designed ridge peaks

`peaks` is the primary silhouette control. Every peak contains:

- `position`: lateral position across the range, normally from `-1` to `1`.
- `height`: relief added above `ridge_base_height`.
- `width`: normalized lateral breadth.
- `asymmetry`: different left/right breadth; `0` is symmetric and the supported
  range is `-0.95` to `0.95`.

The peak contributions blend into one continuous ridge. With noise amplitude
set to zero, these values still produce the complete hill silhouette.

For a composition requiring a specifically authored horizon,
`ridge_profile` replaces additive peaks with ordered `{position, height}`
control points. Smooth interpolation preserves every authored summit and
valley without averaging them into a flat line. The active distant-hill layer
uses this mode to follow the low, broken, unequal rhythm of the Monet reference.

## Front-to-back form

`cross_section.ridge_position` locates the ridge between the front edge (`0`)
and rear edge (`1`). `front_power` and `back_power` independently shape the two
slopes. This gives each band physical depth rather than making it a vertical
backdrop.

## Perlin irregularity

The `noise` object supplies deterministic gradient-Perlin fBm:

- `seed`
- `amplitude`
- `frequency`
- `octaves`
- `persistence`
- `lacunarity`

Noise is multiplied by the cross-section envelope, keeping both band edges at
the configured base elevation. `amplitude: 0` removes irregularity without
removing or flattening the explicitly designed ridge.

## Horizon tree line

`tree_line` is an optional subordinate detail anchored to one named active hill
layer. It does not alter the ridge mesh. The configured count is distributed
across `lateral_range`, mostly in irregular clusters, and placed just behind
the ridge using `ridge_depth_offset` and `depth_jitter`.

`height` and `crown_radius` define rounded deciduous silhouettes.
`evergreen_fraction`, `evergreen_height`, and `evergreen_crown_radius` mix in
narrower tiered conifer silhouettes. Separate deciduous and evergreen
reflectance variants supply dark foliage-green tonal variation. Cluster count,
spread, and clustered fraction create real gaps rather than a continuous hedge.
This mechanism is intended for a remote broken tree line, not for foreground
specimen trees or the future reusable-object system.

## PBRT-v4 Art Studio

The **Distant Hills** inspector exposes the module switch and selectors for the
configured depth layers and their individual peaks. It provides exact controls for
placement, band size, ridge and slope form, peak position/height/width/
asymmetry, noise amplitude/frequency, layer reflectance, and the horizon tree
line's enable/count/size controls. Manual edits to the same JSON remain equally
valid.
