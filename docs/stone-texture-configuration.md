# Procedural stone surface

The existing `rock_scatter` entry accepts `construction.texture` with
`enabled: true` and `generator: "granite"`. Its generic Parameter Values page
exposes these controls after reopening Art Studio. The implementation is in
`stone_texture.py`; it uses PBRT's procedural textures without image assets.

- `grain_size`: positive spatial scale of the fine mineral pattern.
- `mottle_size`: positive spatial scale of broad color variation.
- `grain_strength`: blend from the rock's existing reflectance variant (0)
  toward the mineral pattern (1).
- `grain_dark`, `grain_light`: three-channel mineral reflectances within 0–1.
- `bump_height`: nonnegative amplitude of fine surface bump, in scene units.
  Zero retains the color texture with a smooth surface normal.

The surface is a diffuse material with two scales of three-dimensional Perlin
noise. Conservative affine noise mappings keep color interpolation amounts
within 0–1. Fine noise also drives PBRT bump mapping. This is a granite-like
surface treatment, not a mineralogical simulation or an angular rock generator.
The stone geometry, silhouettes, and instance transforms do not change.

Omitting or disabling `texture` retains the previous rock material path.
The current enabled treatment uses diffuse reflection; it does not add a wet
coating. Texture generation is deterministic and source code is included in
the normal render snapshot. PBRT/CUDA itself is unchanged.
