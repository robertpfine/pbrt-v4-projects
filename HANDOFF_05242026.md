# pbrt-v4-projects — Session Handoff Document
# Last updated: 2026-05-23

## REPO
https://github.com/robertpfine/pbrt-v4-projects
Branch: main
Legacy work preserved on: legacy branch

---

## MACHINE
- OS: Ubuntu 22.04, hostname HotCoffee
- GPU: RTX 5090
- pbrt binary: /home/rpf4/pbrt-v4/build/pbrt
- Projects root: ~/my-pbrt-projects/
- Archive (local, gitignored): ~/my-pbrt-projects/Archive/
- Google Drive sync: gdrive:wipImages/pbrt-v4

---

## REPO STRUCTURE
```
my-pbrt-projects/
├── HANDOFF.md
├── render_pipeline.sh          <- root-level, shared across all projects
├── .gitignore
└── rgbgrid-medium/
    ├── config.json
    ├── build_scene.py
    └── scene_files/
        ├── scene.pbrt          <- generated, gitignored
        ├── volumes/
        │   └── rgbgrid.pbrt   <- generated, gitignored
        ├── meshes/             <- .gitkeep
        └── textures/           <- .gitkeep
```

---

## PIPELINE
Single command from repo root:
```bash
./render_pipeline.sh rgbgrid-medium
```

Steps:
1. Reads rgbgrid-medium/config.json
2. Validates project name matches config.project.name
3. Runs build_scene.py (if pipeline.build_scene.enabled=true)
4. Runs pbrt with --gpu --stats flags
5. Archives 5-file bundle to local Archive/
6. Syncs to Google Drive (if pipeline.rclone_sync.enabled=true)

Archive bundle: PNG, .pbrt, config.json, build_scene.py, render_pipeline.sh
All timestamped: rgbgrid-medium_YYYYMMDD_HHMMSS_*

---

## BUILD PIPELINE (build_scene.py)
Generates two files from config.json:
1. scene_files/volumes/rgbgrid.pbrt — MakeNamedMedium "rgb_vol" block
2. scene_files/scene.pbrt — complete pbrt-v4 scene

### Script structure (7 sections):
1. Utility functions (fmt_floats)
2. wavelength_to_rgb — 380-700nm to RGB
3. compute_rgbgrid — builds sigma_s/sigma_a/le_flat voxel arrays
4. write_medium — generates rgbgrid.pbrt
5. Scene block writers — one function per pbrt concept
6. write_scene — assembles scene.pbrt in correct pbrt order
7. main — entry point, accepts config path as argument

### Python dependencies:
- noise (pip install noise) — Perlin noise for voxel modulation

### Correct pbrt-v4 scene order (critical):
```
MakeNamedMedium "fog"       <- fog declaration (if enabled)
MediumInterface "" "fog"    <- camera born inside fog (if enabled)
LookAt ...
Camera ...
Sampler ...
Integrator ...
Film ...
WorldBegin
    Include "scene_files/volumes/rgbgrid.pbrt"
    LightSource ...
    AttributeBegin
        MediumInterface "rgb_vol" ""   <- before Material
        Material "interface"
        Translate / Rotate ...
        Shape ...
    AttributeEnd
```

---

## KEY pbrt-v4 LESSONS LEARNED
- Include for rgbgrid medium goes INSIDE WorldBegin, not before it
- MediumInterface must come BEFORE Material in AttributeBegin block
- Fog MakeNamedMedium and MediumInterface must come BEFORE LookAt/Camera
  so the camera is "born" inside the fog
- MediumInterface "" "fog" — empty string first = exterior medium is fog
- rgbgrid bounding box (p0/p1) is always world-space axis-aligned —
  rotating the container has no effect on the voxel grid
- Box container uses trianglemesh (NOT bilinearmesh) — winding must be
  inward-facing (clockwise from outside) for medium containment
- bilinearmesh is fragile for medium containment; use trianglemesh instead
- Cylinder shape has no end caps — use spheres at joints for branching geometry
- pbrt native box primitive does not exist — use trianglemesh with 8 vertices
- Distant light is correct for sunlight simulation (parallel rays, from/to)
- rgbgrid supports volumetric emission via "rgb Le" and "float Lescale" params
- Emissive volumes need high pixel_samples (512+) to resolve cleanly

---

## CONFIG.JSON STRUCTURE
Key sections and their roles:
- project — name (must match CLI argument), remote_archive_path
- runtime — pbrt_binary, use_gpu, show_stats
- pipeline — build_scene.enabled, rclone_sync.enabled
- scene.camera — look_at (eye, look, up), fov
- scene.sampler — type, pixel_samples
- scene.integrator — type, max_depth
- scene.film — x_resolution, y_resolution, output_filename
- scene.fog — enabled, sigma_a, sigma_s, g
- scene.lights[] — enabled, type, color_mode, temperature, scale, position
- scene.geometry[] — enabled, label, material, medium, transform, shape
- scene.grid — nx, ny, nz, axis, sigma_a, world_min, world_max
- scene.grid.emission — enabled, le_scale
- scene.grid.noise — enabled, mode, position{}, density{}
- scene.zones[] — enabled, position, wavelength, width, strength

### Noise config structure:
```json
"noise": {
  "enabled": true,
  "mode": "position",
  "position": {
    "frequency": 1.5,
    "amplitude": 0.3,
    "octaves": 4,
    "persistence": 0.5,
    "lacunarity": 2.0
  },
  "density": {
    "frequency": 2.0,
    "amplitude": 0.8,
    "octaves": 6,
    "persistence": 0.6,
    "lacunarity": 2.0
  }
}
```

### Emission config structure:
```json
"emission": {
  "enabled": false,
  "le_scale": 0.01
}
```

### Enabled flags:
Every object has "enabled": true/false for non-destructive toggling.
Use disabled zones/lights to preserve parameter sets for reuse.

### Comment convention:
JSON has no native comments. Use "_comment_zonename" keys with string
values adjacent to the section being documented. build_scene.py ignores
unknown keys.

### Supported light types: infinite, point, spot, distant
### Supported material types: diffuse, interface
### Supported shape types: sphere, disk, trianglemesh, box, cylinder

---

## COORDINATE SYSTEM
- Y-up
- -Z goes into the scene (away from camera)
- Camera at [0, 0, 10] looking at [0, 3.0, 0], FOV 70 degrees

---

## ACTIVE ARTISTIC PROJECT: rgbgrid-medium
Concept: Sky-like volumetric color — horizontal spectral bands evoking
cloud streaks or atmospheric color above a ground plane.

### Current scene setup:
- Film: 1500x1000 (test renders at 500x333, 128 samples)
- Camera: eye [0, 0, 10], look [0, 3.0, 0], fov 70
- Sampler: halton, 512 pixel_samples
- Integrator: volpath, max_depth 80
- Light: distant from [0, 2, 10] to [0, 0, 0], 5500K, scale 2.0 (currently disabled)
- Fog: disabled
- Ground plane: disk radius 20, y=-1.0, diffuse warm gray, rotated 90 on X
- Volume box: trianglemesh, x=+-18, y=-2 to 16, z=-9 to -1
- Grid: 256x64x128, axis=Y, sigma_a=0.4, bounds match box exactly

### Current zone setup (4 spectral bands along Y axis):
- position 0.2, wavelength 650nm (red)
- position 0.4, wavelength 580nm (yellow)
- position 0.6, wavelength 510nm (green)
- position 0.8, wavelength 450nm (blue)
- width 0.15 (overlapping), strength 12.0

### Noise:
- mode: position
- position frequency 1.5, amplitude 0.3, octaves 4, persistence 0.5, lacunarity 2.0
- density frequency 2.0, amplitude 0.8, octaves 6, persistence 0.6, lacunarity 2.0

### Emission:
- Currently enabled with le_scale 0.01, distant light disabled
- Emissive mode is promising but needs tuning — high samples required
- Non-emissive mode (distant light enabled) also strong

---

## NEXT SESSION WORK
- Tune emissive rgbgrid parameters (le_scale, pixel_samples)
- Explore combining emission + distant light
- Port space colonization algorithm from C++ to Python for branching
  foreground geometry
- Space colonization output: cylinder per branch segment + sphere at each
  node to cover joints
- Robert has existing C++ implementation (Peter Shirley rendering
  infrastructure) outputting cylinder portfolios — retrieve from Windows 11
  build machine

---

## GIT COMMIT DISCIPLINE
- Commit after structural changes to build_scene.py or render_pipeline.sh
- Commit when a stable working milestone is reached
- Do NOT commit after every parameter tweak — Google Drive archive handles that
- Always push to main after committing
- config.json committed reflects the stable state at that milestone

---

## WORK SESSION CONVENTIONS
- Go one step at a time — always get confirmation before proceeding
- Code in Python unless otherwise noted
- Always specify exactly what to change and where — nothing ambiguous
- Explicit Ctrl+S to save files — VS Code does not auto-save on render
- Test renders: 500x333, 128 samples before committing to full resolution
- Production renders: 1500x1000, 256+ samples
- Target output: Epson P9000, Hahnemuhle Fine Art Baryta, 36" wide format

---

## FUTURE PROJECTS
Additional projects will sit at the same level as rgbgrid-medium/.
Each project has its own config.json and build_scene.py.
render_pipeline.sh at repo root is shared across all projects.
Call: ./render_pipeline.sh <project-name>
