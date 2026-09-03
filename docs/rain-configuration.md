# Rain-Curtain Configuration

The live rain controls are in one discoverable block: `scene.rain`, directly
after `scene.fog` in `scene_workspace/config.json`. Rain is independent of the
cloud shape controls under `scene.sky.clouds`.

`enabled` turns every configured shower on or off. `appearance` controls the
PBRT medium: `density`, RGB `scattering`, RGB `absorption`, and phase-function
`anisotropy`. These determine visibility and color, not the curtain's shape.

`pattern` controls the visible rain structure. `broad_frequency` makes the
large uneven sheet; `streak_frequency` makes narrow, vertically coherent
columns. The deliberately low Y frequencies keep those columns vertical.
`coverage` and `softness` control how much of the box becomes rain and how hard
the internal streak edges are. `base_density` and `contrast` control the broad
density variation. `wind_tilt_degrees` and `wind_direction_degrees` lean the
columns. `edge_fade_fraction` fades X, Y, and Z box faces so the bounded volume
does not read as a rectangle.

Each entry in `curtains` has an independent `center`, `size`, and voxel
`resolution`. It may override either `appearance` or `pattern`. The first study
uses one curtain named `left_cloud_distant_shower`, centered below the large
left cumulus. Its top meets the cloud base; its bottom reaches the distant
ground. Individual raindrop geometry is not part of this distant-volume study.
