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

The retained configuration currently contains one `broad_rise` height field.
The whole module is disabled in the artist-accepted `054517` composition, so
the meadow meets the mottled vista plane directly. The complete rise definition
remains available for reversible comparisons; setting the module-level
`enabled` value to `true` restores the hill and its targeted vegetation
extensions.

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
`ridge_profile` can replace additive peaks with ordered `{position, height}`
control points. Smooth interpolation preserves every authored summit and
valley without averaging them into a flat line. The retained `broad_rise` uses
one broad, off-center peak instead of a ridge profile.

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

## Ground-detail extensions

Grass and poppies remain owned by their discoverable ground-detail blocks. An
optional `extension` inside either block targets one named distant-hill layer:

- `target_distant_hill` selects the receiving layer.
- `count`, `seed`, `scale`, `max_slope_degrees`, `y_offset`, and `patchiness`
  control the secondary population.
- `lateral_range` and `depth_range` select normalized areas of the hill.
- `ridge_fade` gradually reduces density before the crest, avoiding a hard
  vegetation outline against the sky.

The retained grass extension contains 2,500,000 tufts and the poppy extension
contains 2,500 smaller plants. Both target `broad_rise`, and both become
inactive automatically while the distant-hills module is disabled. Render
`053150` verifies poppies on both the foreground meadow and `broad_rise`.

## Horizon tree line

`tree_line` is an optional, currently unused subordinate detail anchored to one named active hill
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

## Current visual checkpoint

Render `054517` is the artist-accepted hill-disabled comparison. Its archived
JSON matches the live configuration, and its PBRT file contains no distant-hill,
distant-grass, or distant-poppy blocks. Render `054050` is not a valid
comparison: an older in-flight builder generated hill geometry and later copied
newer JSON into the archive bundle. Do not use `054050` as reproducibility
evidence.
