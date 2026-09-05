# Cloud boundary controls

The cloud system has two boundary modes. `axis_aligned` preserves every
existing scene and remains the default when `boundary` is absent.
`corner_prism` is the precise composition tool for bringing a finite overcast
deck to the visible horizon without approximating the bottom with one
`far_y_offset` value.

## Corner-prism configuration

Add `boundary` beside `placement` and `dimensions` in one cloud object:

```json
"boundary": {
  "mode": "corner_prism",
  "bottom_corners": {
    "near_left":  [-25000.0,  1200.0,   10000.0],
    "near_right": [ 25000.0,  1200.0,   10000.0],
    "far_right":  [ 25000.0,    90.0,  -60000.0],
    "far_left":   [-25000.0,    90.0,  -60000.0]
  },
  "thickness": 2500.0
}
```

These are world-space coordinates. `near` and `far` describe the intended
camera-facing order; they do not require a particular sign of Z. The four
names must trace the footprint perimeter in this order:

```text
near_left -> near_right -> far_right -> far_left -> near_left
```

The footprint may be a skewed convex quadrilateral. All four bottom points
must lie on one plane. This deliberate restriction prevents a twisted quad
whose two triangles and density support would disagree along a diagonal.
The system derives each top corner by adding `[0, thickness, 0]`, producing a
closed eight-vertex, twelve-triangle vertical prism.

Plane-following 3D noise is anchored at the midpoint of the near bottom edge.
This matches the zero-offset end of the legacy depth slope, allowing an
equivalent rectangular slope to be converted without shifting its noise field.

In this mode the explicit corners and thickness control the boundary and the
density-grid bounds. Existing `placement.position` and `dimensions` remain in
the first-generation schema for compatibility and easy return to
`axis_aligned`; they do not override the prism. A lobed generator still uses
`placement.position` as its lobe anchor.

`density_field.depth_slope.enabled` must be `false` with `corner_prism`.
The two controls are alternative geometry models, not cumulative tilts.

## Independent face fades

For a `mottled_veil`, replace the symmetric legacy XYZ fade triple with:

```json
"edge_fade_fraction": {
  "left": 0.08,
  "right": 0.08,
  "bottom": 0.15,
  "top": 0.15,
  "near": 0.10,
  "far": 0.0
}
```

Each value is the fraction of the prism measured inward from that face over
which density rises smoothly. Values must be between `0` and `1`. In this
explicit form, `0` disables the density fade at that face. That is useful for a
far face deliberately placed beyond the frame, but an abrupt face can become
visible if it enters the camera view.

The old `[x, y, z]` form remains valid and maps symmetrically:

- X to left and right;
- Y to bottom and top;
- Z to near and far.

## Validation before grid generation

Scene validation and scene construction reject a corner prism when:

- a named corner is missing or is not a finite vec3;
- thickness is not positive;
- the XZ footprint is crossed, concave, or has zero area;
- the four bottom points are not coplanar;
- `depth_slope` is also enabled; or
- any enabled cloud boundary contains the configured camera eye.

The camera check applies to legacy axis-aligned boxes as well as corner prisms
and runs before the expensive cloud grid is generated. This
prevents the accidental camera-inside-volume state associated with extremely
slow or apparently unbounded volumetric renders.

## Camera-frame projection diagnostic

Inspect the current enabled overcast boundary without building PBRT or starting
a render:

```bash
./cloud_boundary_diagnostic.py --cloud overcast_cloud_deck
```

The command prints the camera-inside state and the pixel position, forward
depth, and in-frame state of every bottom and top vertex. It uses PBRT's default
perspective screen-window convention, including portrait and landscape film
aspect ratios.

To create a wireframe at the configured film aspect and resolution:

```bash
./cloud_boundary_diagnostic.py \
  --cloud overcast_cloud_deck \
  --svg /tmp/overcast-boundary.svg
```

The SVG is a geometry diagnostic, not a rendered image: it shows projected
prism edges even when the density at those edges is faded to zero. `--json`
provides the same measurements in machine-readable form.

## Perspective limit

No finite overhead plane literally intersects the mathematical horizon in a
perspective camera. Practical coverage comes from some combination of:

- lowering the far bottom vertices toward camera/ground height;
- putting the far and side faces outside the frame;
- extending the footprint far enough that the remaining gap is subpixel; and
- using a separate distant horizon veil if an effectively infinite deck is
  required.

The corner prism makes the first two operations explicit and measurable. It
does not remove that perspective constraint.

## Generator implementation

The Python reference and compiled C++ grid builder implement the same rules.
Both create an axis-aligned PBRT grid enclosing the prism, assign zero density
to voxels outside the prism, follow the authored bottom plane when evaluating
vertical density and underside optics, and use the explicit prism mesh as the
medium boundary. Automated parity tests cover a tilted, skewed prism with
asymmetric face fades and RGB underside grids.
