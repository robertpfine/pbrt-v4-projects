# Sunflower plants and fields

Sunflowers use the original Vogel/area-dome head and support generators from
`aebaff1`. The implementation is independent of Claude's archived September 8
sunflower experiment; that archive was not consulted.

## Ownership and controls

Add a `generator: "sunflower"` surface-object entry under the active
terrain-heightfield landform in the sole live `scene_workspace/config.json`.
The existing Art Studio entry form exposes the whole entry automatically.
This does not migrate the land-cover mapping or introduce an asset registry.

`construction.pattern` is the original sunflower recipe: floret zones,
petals, backing, bracts, head pitch, stalk, and leaves. Its support and stalk
must be enabled. The stalk's length and radii, leaf size/count/profile, and
all head details remain manually editable. Leaves use the original curved
petal mesh; detailed heart-shaped blades, serrations, and petioles are not
implemented in this first field study.

`construction.variants` specifies the number of complete plant prototypes.
`head_pitch_variation` adds a symmetric angle range around the recipe's head
pitch. `stem_length_variation` adds a symmetric fractional length range.
Variants are deterministic and evenly spaced across these ranges.

`population.method` selects:

- `scatter`: use `count`, `seed`, `region.center` / `region.size` (world XZ),
  `scale`, `max_slope_degrees`, `y_offset`, and the established patchiness and
  root-based camera-frustum scatter controls. `heading_degrees` sets the common
  Y rotation, with variation of ±`heading_spread_degrees`. There is no minimum
  plant spacing; heads can overlap. Region/slope filters must yield the full
  requested count or building fails with an explicit diagnostic.
- `explicit`: each item in `instances` supplies a world-XZ `position`, a Y
  offset above sampled terrain, `rotation_degrees` about Y, positive uniform
  `scale`, and zero-based `variant`. `population.y_offset` also applies.
  Scatter count, heading, and scale-range controls are inactive in this mode.

Each complete plant is rooted at local zero and kept upright along world Y.
The emitter samples ground height but does not lean plants with the terrain
normal or apply the generic scatter's anisotropic aspect changes. A heading
of zero faces a near-vertical sunflower head toward positive Z. Explicit
placements outside their landform and invalid field controls are rejected.

## PBRT and reproducibility

`sunflowers.py` calls the existing head/support writer, expands its generated
organ instances once per plant variant, then emits one PBRT `ObjectBegin`
prototype per variant and one `ObjectInstance` per field plant. Expansion is
necessary because PBRT-v4 forbids nested instances. Existing isolated-head
output and the disabled original head recipe are preserved.

The standard immutable render snapshot includes `sunflowers.py` in its source
bundle automatically. Use the archived source bundle and JSON to reproduce a
render; generated environment maps follow the existing regeneration workflow.

## First independent proof

Single-plant render `Sunflower_Plant_Study_20260908_033451.png` completed at
800×900, 16 samples, with one explicit placement. It verifies whole-plant
geometry, ground contact, original spiral-head detail, and legal PBRT
instancing. This is an exploratory proof, not an artist-accepted master.

Field render `Sunflower_Field_Study_20260908_034127.png` completed at
1600×1200, 32 samples. Its PBRT contains exactly three whole-plant prototypes
and 500 instances. The live configuration matches its archived JSON exactly;
the source archive contains the verified `sunflowers.py` implementation.
Both completed PNGs were inspected locally. The field remains a first artistic
study awaiting the artist's evaluation.
