# Sky environment configuration

The authoritative controls are in `scene_workspace/config.json` under
`scene_description.sky.background`. The supported PBRT `type` is `infinite`.
`source` is `uniform` (also the default when omitted) or `procedural_overcast`.
The latter supports `environment.generator: "overcast_map"`. A third source,
`procedural_twilight`, uses `environment.generator: "twilight_map"`.
This background is an environment light: it supplies visible sky and scene
illumination without a surface or participating medium. The separate sun is a
PBRT `distant` light; local cloud volumes remain under `sky.clouds`.

The environment controls are directly editable JSON:

- `resolution`: square map dimensions, at least 512 by 512; current 2048 square.
- `seed`: deterministic pattern selection.
- `coverage`: quantile-based cloud coverage, from zero to one.
- `softness`: positive transition width; larger values soften boundaries.
- `broad_feature_fraction`, `medium_feature_fraction`, and
  `detail_feature_fraction`: positive angular feature controls; larger values
  produce broader structure.
- `horizon_bias`: shifts the cloud signal toward the horizon.
- `contrast`: cloud tone separation; the current value 6 is an extreme study.
- `clear_color`, `cloud_dark_color`, `cloud_light_color`: non-negative RGB
  inputs for clear regions and cloud tones.
- `target_average_color`: channel normalization target before final clipping.
- `rotation_degrees`: rotates the environment around world Y.

The enclosing background `scale` multiplies environment illumination. Its
uniform `color` is retained but is not used as map radiance in procedural mode.
The generator writes linear RGB `overcast_environment.pfm` and a display-encoded
`overcast_environment_equalarea.png` under the generated texture directory.

Current limitations: output is clipped to [0,1] after mean normalization, so
extreme colors/contrast can prevent the final map from attaining its target
average and discard HDR values. No dedicated new Qt controls were added in
this checkpoint. The source archive freezes the generator and configuration,
but excludes generated texture output; regenerate maps before replaying an
archived PBRT scene. The checkpoint preserves this implementation as found.

## Twilight gradient

`procedural_twilight` supplies a smooth environment gradient, with world Y up.
It uses the same square equal-area map dimensions and enclosing background
`scale`. Its controls are non-negative linear RGB `zenith_color`,
`horizon_color`, and `nadir_color`, plus `horizon_transition_degrees` in (0,90].
The gradient smoothly reaches the upper/lower color at that elevation above
or below the horizon. The horizon glow extends around the full scene; this
is an artistic twilight approximation, not an astronomical atmosphere model.
The existing sun and volumetric clouds remain independent.

The generator writes `twilight_environment.pfm` and a display-encoded
`twilight_environment_equalarea.png`. Retained overcast pattern controls and
the enclosing uniform `color` are inactive in this mode. The map is regenerated
from archived configuration and source when replaying a scene. Reopen Art
Studio to expose newly added fields through the generic entry form.

Optional stars use `star_count` (0–2000, default 0), `seed`,
`star_radius_degrees` (positive, at most 1, default 0.08), and `star_brightness`
(positive peak linear radiance, default 8). Seeded directions remain the same
across resolutions. The small Gaussian points fade toward the horizon and
appear only above eight degrees elevation. These are an artistic star field,
not a star catalogue. The PFM preserves their HDR values; the PNG map preview
clips them for display. At low render resolution/sampling, tiny stars can be
softened or missed by texture filtering.
