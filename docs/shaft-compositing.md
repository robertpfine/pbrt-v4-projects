# Volumetric Shaft Compositing

`render_shaft_composite.py` separates cloud-filtered sunlight from its direct
illumination of scene surfaces.

It renders two PBRT-v4 passes:

1. A base pass with the added `shaft_sun` and aperture disabled.
2. A shaft pass containing only `shaft_sun`, the aperture, the atmosphere, and
   non-reflective scene surfaces. The black surfaces still occlude light but do
   not contribute bright ground or foliage patches.

The shaft pass is blurred slightly and added to the base image in linear RGB.
The result retains PBRT's volumetric transport while allowing atmospheric
shafts to be controlled independently of ground illumination.

Configuration is under `pipeline.shaft_composite`:

```json
"shaft_composite": {
  "enabled": true,
  "shaft_light": "shaft_sun",
  "base_opacity": 0.30,
  "shaft_opacity": 0.85,
  "surface_reflectance_scale": 0.20,
  "terrain_reflectance_scale": 0.05,
  "blur_radius": 1.0
}
```

- `shaft_light` names the labeled distant light isolated in the shaft pass.
- `base_opacity` scales the original scene contribution.
- `shaft_opacity` scales the atmospheric shaft contribution.
- `surface_reflectance_scale` controls tree and other non-terrain reflectance
  in the shaft pass.
- `terrain_reflectance_scale` independently controls terrain reflectance in the
  shaft pass, allowing it to remain darker than the tree.
- `blur_radius` applies a small pixel-space Gaussian blur before compositing.

Run from the repository root:

```bash
python3 render_shaft_composite.py rgbgrid-medium
```

The base and shaft PNGs are retained as internal diagnostic passes, while the
composite PNG is the final image presented for evaluation. `Archive/` also
receives the config, scene builder, standard render pipeline, composite script,
both PBRT scene files, and this documentation so every composite is
reproducible. Composite renders therefore retain the traditional five archive
file types—PNG, PBRT, JSON, Python, and shell script—plus the extra files needed
for the two-pass composite.
