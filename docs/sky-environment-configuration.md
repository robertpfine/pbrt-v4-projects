# Sky environment configuration

The authoritative controls are in `scene_workspace/config.json` under
`scene_description.sky.background`. The supported PBRT `type` is `infinite`.
`source` is `uniform` (also the default when omitted) or `procedural_overcast`.
The latter currently supports one `environment.generator`, `overcast_map`.
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
