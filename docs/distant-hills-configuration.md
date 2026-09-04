# Distant Hills Configuration

Each distant hill is an independent entry in `scene_description.landforms` in
the one authoritative `scene_workspace/config.json`, selected by
`topography.generator: "distant_ridge"`. It generates a real world-space
triangle mesh with front slopes, a designed ridge, and a rear slope.

## Module and layers

Each landform's `enabled` value switches that ridge independently. Separate
landform entries provide independently editable depth layers, each with its own
placement, silhouette, surface irregularity, and color.

- `placement.position`: world-space center and base elevation.
- `placement.rotation_degrees[1]`: rotation in the ground plane.
- `geometry.patches[0].dimensions`: band `[width, depth]` before rotation.
- `geometry.patches[0].subdivisions`: mesh vertices across width and depth.
- `topography.parameters.ridge_base_height`: continuous relief beneath all
  designed peaks.
- `shading_normal_up_blend`: optional distant-layer lighting softener. Values
  near `1` suppress harsh grazing-angle contrast while retaining the geometric
  silhouette; it is used for strongly atmospheric far ranges, not foreground
  terrain.
- `surface.material.reflectance`: RGB surface reflectance for the layer.

The retained configuration currently contains one `broad_rise` height field.
The landform is disabled in the artist-accepted `054517` composition, so
the meadow meets the mottled vista plane directly. The complete rise definition
remains available for reversible comparisons; setting the landform's `enabled`
value to `true` restores the hill and its targeted vegetation
extensions.

## Designed ridge peaks

`topography.parameters.peaks` is the primary silhouette control. Every peak contains:

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

`topography.parameters.cross_section.ridge_position` locates the ridge between the front edge (`0`)
and rear edge (`1`). `front_power` and `back_power` independently shape the two
slopes. This gives each band physical depth rather than making it a vertical
backdrop.

## Perlin irregularity

The `topography.parameters.noise` object supplies deterministic gradient-Perlin fBm:

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

Grass and poppies remain owned by `flat_landform.surface_objects[]`. An optional
`population.extension` inside either object targets one named distant-ridge landform:

- `target_distant_hill` selects the receiving layer.
- `count`, `seed`, `scale`, `max_slope_degrees`, `y_offset`, and `patchiness`
  control the secondary population.
- `lateral_range` and `depth_range` select normalized areas of the hill.
- `ridge_fade` gradually reduces density before the crest, avoiding a hard
  vegetation outline against the sky.

The retained grass extension contains 2,500,000 tufts and the poppy extension
contains 2,500 smaller plants. Both target `broad_rise`, and both become
inactive automatically while the target landform is disabled. Render
`053150` verifies poppies on both the foreground meadow and `broad_rise`.

## Horizon tree line

The earlier `tree_line` experiment is not present in the retained configuration.
If restored, it belongs as a surface object anchored to one named active ridge
landform; it does not alter the ridge mesh. Its configured count is distributed
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

The **Distant Hills** inspector selects the configured ridge landforms and their
individual peaks. It provides exact controls for
placement, band size, ridge and slope form, peak position/height/width/
asymmetry, noise amplitude/frequency, and landform reflectance. Manual edits to
the same JSON remain equally valid.

## Current visual checkpoint

Render `054517` is the artist-accepted hill-disabled comparison. Its archived
JSON matches the live configuration, and its PBRT file contains no distant-hill,
distant-grass, or distant-poppy blocks. Render `054050` is not a valid
comparison: an older in-flight builder generated hill geometry and later copied
newer JSON into the archive bundle. Do not use `054050` as reproducibility
evidence.
