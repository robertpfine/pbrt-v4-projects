# Pond surfaces and water lilies

`pond.py` adds a bounded still-pond study to the existing landform/entry model.
The sole live scene remains `scene_workspace/config.json`. No asset registry,
saved-type library, or general placement migration is introduced.

## Art Studio controls

**Scene > Landforms > lily_pond** exposes the water's construction and optics.
**Scene > Land cover > pink_and_white_water_lilies · on lily_pond** exposes
the plants' construction and population. Both pages come from the generic
entry form builder. Reopen Art Studio after these new entries are introduced;
Reload JSON does not yet rebuild entry pages. Existing sunflower recipes are
retained disabled, and the pre-pond live scene is checkpoint `c99c3f4`.

## Pond landform

- `placement.position` and the one enabled plane patch's `local_position`
  locate the water. Both rotation triples must currently be zero.
- Patch `dimensions` are width/depth; `subdivisions` control the surface mesh.
- `topography.generator: "pond_surface"` evaluates the still water surface.
- `parameters.depth` is the absorbing water volume's depth, in scene units.
- `parameters.ripples[]` holds amplitude, wavelength, direction, and phase.
  Direction 0 runs along X, 90 along Z; angles are degrees. Waves are static
  sums of sinusoids, smoothly fading to zero at the rectangular pond rim.
- `surface.material` specifies dielectric `eta`, reflection `roughness`, and
  three RGB `absorption` coefficients per scene unit. A closed medium volume
  beneath the rippled surface provides depth-dependent transmission color.
  The study has no water scattering or animated waves.
- The existing mandatory terrain heightfield serves as the submerged bed.
  Its settings are distinct from the water surface. The initial study used a
  flat bed; the morning landscape uses the optional terrain `basin` controls
  in `rolling_pond_banks` to excavate a pond bed and blend into rolling banks.
  The water remains rectangular underneath opaque dry land. Keep its entire
  perimeter buried and the lily footprints over submerged terrain: lily
  placement currently checks water bounds, not shoreline clearance.

The rocky-shore comparison adds `basin.shore` to keep the immediate land near
water level before blending back into distant hills. `shoreline_rocks` on
`rolling_pond_banks` uses the existing `rock_scatter` construction: rounded
spheres varied by instance scale, aspect, rotation, and color. It is not yet
an angular or fractured-rock generator. Its population `elevation_range`
selects a thin band around the waterline; `y_offset` partially buries the
stones. `shore_trees` reuses the established fractal tree with three explicit,
terrain-sampled placements. The original tree recipe remains disabled under
the flat landform. The rock entry is relocated to the shore because snapshot
validation currently permits only one rock entry across all landforms; its
earlier settings are preserved in checkpoint `9ad6b6e`. Reopen Art Studio to
expose these entries.

The stone surface can now use `construction.texture.generator: "granite"`
for fine mineral grain, broad mottling, and bump relief; see
[`stone-texture-configuration.md`](stone-texture-configuration.md). This changes
the surface treatment while retaining the existing rounded geometry.

## Water-lily construction

A `generator: "water_lily"` entry belongs to the pond's `surface_objects`.
Each prototype is a cluster of notched round pads and optionally a blossom.

- `variants` is the number of deterministic geometric/color variants. Each
  has both flowering and pad-only prototypes; copies use whole-cluster PBRT
  instancing without nested ObjectInstance declarations.
- `pads_per_cluster`, `pad_radius`, and `cluster_radius` control pad number,
  size, and distance from the flower center.
- `pad_notch_degrees`, `pad_camber`, `pad_segments`, and `pad_rings` control
  the wedge opening, shallow curvature, and mesh detail.
- `vein_count`, `vein_width` (half-width), `pad_color`, `vein_color`, and
  `roughness` control the pad surface and raised radial vein ribbons.
- `flower_radius`, `flower_height`, `petal_width` (maximum half-width),
  `petal_layers`, `petals_per_layer`, and `petal_segments` control the blossom.
  Inner whorls rise more steeply than outer whorls. `stamen_count` and
  `center_color` control the golden center.
- `petal_color` blends toward `petal_tip_color` along each pointed petal;
  every third prototype has a stronger ivory contribution for the requested
  pink-and-white mix. RGB reflectances must lie within 0–1.

## Water-lily placement

- `method: "scatter"`: `count` counts clusters, not individual pads or petals.
  `seed` makes placement repeatable; `region.center` / `size` are world XZ.
  `scale` is the uniform scale range; `minimum_spacing` separates cluster
  centers. It does not guarantee that all pad outlines avoid overlap.
- `flower_probability` controls the fraction of clusters with blossoms.
- `method: "explicit"`: each `instances[]` item gives world-XZ `position`,
  positive `scale`, Y `rotation_degrees`, zero-based `variant`, and a `flower`
  boolean. Scatter region/count/spacing/probability controls are inactive.
- `surface_offset` lifts each cluster above the sampled water height.
  Clusters remain horizontal; individual pads do not deform with ripples.
  Keep ripple amplitudes small relative to pad size and clearance.
- Entire cluster footprints must fit inside the pond. Impossible scatter
  counts and out-of-bounds explicit placements fail with a diagnostic.

The pads and blossoms are a first artistic model: no submerged petioles,
rhizomes, serration system, growth simulation, or physical leaf deformation.
Water lilies currently require pond landforms; other asset-to-landform pairings
remain the subject of the agreed future migration.

## Reproducibility

The normal terminal pipeline freezes `pond.py`, the exact live JSON, and the
builder with the other source files before rendering. Completed PNG/PBRT/config
and source bundles are archived locally and copied through the configured
remote archive workflow. The generic GUI requires no new page implementation.
