# Rain-Curtain Configuration

The live rain controls are self-contained objects in
`scene_description.atmosphere.rain[]` in the sole authoritative
`scene_workspace/config.json`. Rain remains independent of the cloud objects
under `scene_description.sky.clouds[]`.

Each object's `enabled` state controls that shower independently. Its `medium`
owns `density_scale`, RGB `scattering`, RGB `absorption`, and phase-function
`anisotropy`. These determine visibility and color, not the curtain's shape.

`density_field` controls the visible rain structure. `broad_frequency` makes the
large uneven sheet; `streak_frequency` makes narrow, vertically coherent
columns. The deliberately low Y frequencies keep those columns vertical.
`coverage` and `softness` control how much of the box becomes rain and how hard
the internal streak edges are. `base_density` and `contrast` control the broad
density variation. `wind_tilt_degrees` and `wind_direction_degrees` lean the
columns. `edge_fade_fraction` fades X, Y, and Z box faces so the bounded volume
does not read as a rectangle.

Each rain object has its own `placement.position`, `dimensions`, and
`density_field.resolution`; there are no shared appearance or pattern defaults.
The retained study uses one disabled object named
`left_cloud_distant_shower`, centered below the historical large left cumulus.
Its top meets the cloud base; its bottom reaches the distant ground. Individual
raindrop geometry is not part of this distant-volume study.
