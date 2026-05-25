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
4. Runs generate.py (if any tree in scene.trees[] has enabled=true OR foliage enabled)
5. Runs pbrt with --gpu --stats flags
6. Archives 5-file bundle to local Archive/
7. Syncs to Google Drive (if pipeline.rclone_sync.enabled=true)

---

## PYTHON DEPENDENCIES
- noise (pip install noise) — Perlin noise for voxel modulation
- numpy — vectorized distance calculations
- scipy (pip install scipy) — KDTree for nearest-neighbor queries

---

## FILE ROLES
- generate.py — orchestrator, called by render_pipeline.sh
  - imports space_col and foliage
  - iterates over scene.trees[] list
  - for each enabled tree: runs Tree3D, writes tree_N.pbrt
  - for each enabled tree with foliage: runs foliage.run(), writes foliage_N.pbrt
  - no serialization between modules
- space_col.py — space colonization tree algorithm
  - generates tree_N.pbrt (cylinders + joint spheres)
  - write_tree() takes index=N parameter for indexed output filename
- foliage.py — foliage generation
  - Section 1: Imports
  - Section 2: compute_transport_frames() — parallel transport frame
  - Section 3: compute_phyllotaxis_points() — golden angle placement
  - Section 4: LeafBoundary, LeafVenation — 2D venation algorithm
  - Section 5: generate_canonical_leaf(), leaf_to_world(), triangulate_leaf_blade(), make_disk_leaf()
  - Section 6: write_foliage() — pbrt ObjectBegin/ObjectInstance output
  - Section 7: run() — entry point from generate.py
  - run() and write_foliage() take index=N parameter for indexed output filename
  - ObjectBegin names are "tree_N_leaf_M" — globally unique across all foliage files

---

## KEY pbrt-v4 LESSONS LEARNED
- Include for rgbgrid medium goes INSIDE WorldBegin
- MediumInterface must come BEFORE Material in AttributeBegin block
- Box container uses trianglemesh with inward-facing winding
- Cylinder shape has no end caps — use spheres at joints
- rgbgrid supports volumetric emission via "rgb Le" and "float Lescale"
- Instancing: ObjectBegin/ObjectEnd defines geometry once, ObjectInstance places it
- Materials are BAKED into ObjectBegin — cannot vary per instance
- For per-leaf color variation: define N ObjectBegin variants, randomly assign instances
- foliage_N.pbrt can exceed 100MB — keep in .gitignore
- tree_N.pbrt also gitignored
- Distant light correct for sunlight (parallel rays, from/to)
- Grid enabled flag skips both rgbgrid.pbrt generation and Include in scene
- pbrt-v4 does NOT support nested ObjectBegin — leaf instancing inside a
  tree ObjectBegin is illegal. This was confirmed as the forest system blocker.
- ObjectBegin names must be globally unique across ALL included files —
  use "tree_N_leaf_M" naming to avoid collisions when multiple foliage files
  are included in the same scene

---

## INSTANCING ARCHITECTURE
Leaf instancing uses pbrt ObjectBegin/ObjectInstance:
- One ObjectBegin "tree_N_leaf_M" per palette color (M = palette index)
- Geometry (blade triangles + vein ribbons) computed ONCE, reused per color variant
- Only material color differs between variants
- Each phyllotaxis placement randomly assigned to a variant
- 52 seconds at 5000x4000 with 4017 leaves — confirmed production-ready

Tree instancing (PLANNED — Phase 2):
- Nested ObjectBegin is ILLEGAL in pbrt-v4 — confirmed blocker
- When forest instancing is active, foliage must be written as flat geometry
  (no inner ObjectBegin/ObjectInstance for leaves)
- Forest mode and single-tree mode are mutually exclusive via forest.enabled flag

---

## MULTI-TREE PIPELINE STATE (Phase 1 — COMPLETE)
Multiple unique trees fully working:
- config.json uses "trees": [] list — each entry is a full tree block
- Each tree entry has its own nested "foliage": {} block
- generate.py iterates the list, grows each enabled tree independently
- Outputs tree_0.pbrt, tree_1.pbrt ... and foliage_0.pbrt, foliage_1.pbrt ...
- build_scene.py iterates trees list, emits Include for each tree and foliage file
- Trees are placed at their generated root_position — no instancing
- Confirmed working: two unique trees, different seeds, different foliage palettes

To add a tree: copy a full tree block in config.json trees[] array, set new seed
and root_position. Enable/disable per entry with "enabled": true/false.

---

## FOLIAGE SYSTEM STATE
Foliage pipeline fully working:
- Parallel transport frame: compute_transport_frames() — minimizes leaf twist
- Phyllotaxis: golden angle 137.5 degrees, cylindrical model from Algorithmic Botany Ch4
- Venation: 2D space colonization within LeafBoundary (ovate or ellipse)
- Blade: Delaunay triangulation (Option C) — grid sample + boundary filter
- Leaf curvature: midrib_curvature (arch along length), blade_curvature (cup across width)
- Instancing: ObjectBegin/ObjectInstance — one BVH per variant, N transforms

### Palette color variation:
- blade.palette[] — list of {enabled, color} entries
- Active colors = enabled entries only
- Fallback to blade.color if no active palette entries
- One ObjectBegin "tree_N_leaf_M" per active color
- Random variant assigned per placement

### Botanical naming (from Runions papers):
- blade — lamina surface (triangulated mesh)
- vein_color — vein ribbon color (NOT leaf color)
- venation — vein network parameters
- midrib_curvature — arch along leaf length
- blade_curvature — cup across leaf width
- birth_dist — matches bs from venation paper
- D, dk_multiplier, di_multiplier — match Runions notation

---

## CONFIG.JSON KEY SECTIONS

### Current scene setup:
- Film: 1500x1000 (test), 5000x4000 (production)
- Camera: eye [0, 0, 16], look [0, 2.0, 0], fov 70
- Sampler: halton, 256 pixel_samples
- Integrator: volpath, max_depth 80
- Light: distant from [0, 2, 10] to [0, 0, 0], 5500K, scale 4.0
- Fog: disabled
- Ground plane: disk radius 20, y=-1.0
- Volume box: disabled
- Grid: disabled

### Trees config structure:
```json
"trees": [
  {
    "enabled": true,
    "seed": 1,
    "num_leaves": 12000,
    "max_loops": 200,
    "max_stuck": 5,
    "min_leaves": 30,
    "D": 0.2,
    "dk_multiplier": 2.0,
    "di_multiplier": 999.0,
    "birth_dist": 0.15,
    "leaf_width": 1.0, "leaf_height": 1.0, "leaf_depth": 1.0,
    "point_cloud_center": [-4, 5.0, -3.0],
    "point_cloud_radius": 4.0,
    "base_radius": 0.003,
    "trunk_radius": 999,
    "joint_radius_multiplier": 1.3,
    "joint_radius_cap": 0.02,
    "root_position": [-4, 0.5, -3.0],
    "trunk_material": { "type": "diffuse", "reflectance": [0.40, 0.35, 0.10] },
    "joint_material": { "type": "diffuse", "reflectance": [0.40, 0.35, 0.10] },
    "foliage": {
      "enabled": true,
      "internode_distance": 0.3,
      "leaf_angle": 45.0,
      "min_loop_index": 5,
      "max_branch_radius": 0.05,
      "leaf_scale": 0.8,
      "vein_color": [0.15, 0.35, 0.10],
      "leaf": {
        "type": "ovate",
        "length": 1.0,
        "width": 0.5,
        "midrib_curvature": 0.1,
        "blade_curvature": 0.05,
        "min_vein_width": 0.008,
        "show_veins_only": false,
        "blade": {
          "enabled": true,
          "resolution": 20,
          "color": [0.08, 0.25, 0.06],
          "palette": [
            { "enabled": true, "color": [0.08, 0.25, 0.06] },
            { "enabled": true, "color": [0.12, 0.30, 0.05] },
            { "enabled": true, "color": [0.70, 0.60, 0.02] },
            { "enabled": true, "color": [0.10, 0.28, 0.04] }
          ]
        },
        "venation": {
          "D": 0.02,
          "dk_multiplier": 2.0,
          "di_multiplier": 999.0,
          "num_sources": 400,
          "birth_dist": 0.02,
          "max_loops": 100,
          "max_stuck": 5
        }
      }
    }
  }
]
```

NOTE: Yellow test color [0.70, 0.60, 0.02] in tree 0 palette confirms palette
system working. Tree 1 uses rust/orange [0.50, 0.20, 0.02] as distinguishing test color.
Replace both with natural green/autumn variants for production.

---

## NEXT SESSION WORK

### Immediate:
1. Replace test palette colors with natural autumn or green variants
2. Commit palette update

### Forest system — Phase 2 (next major feature):
- Confirmed: pbrt-v4 does NOT support nested ObjectBegin
- When forest.enabled=true, foliage must be written as FLAT geometry
  (no ObjectBegin/ObjectInstance for leaves — raw trianglemesh per leaf)
- One unique tree grown per seed, geometry defined once
- N instances placed via ObjectInstance with world-space transform
- Config: forest.enabled, instances list with explicit positions
- Placement: position, Y rotation, scale per instance
- forest.enabled=false falls back to current multi-tree pipeline exactly

### Sky volume (after forest):
- Re-enable grid (scene.grid.enabled: true)
- Re-enable volume_box geometry
- Composite forest against rgbgrid sky
- Camera positioning for forest + sky composition

### Foliage improvements (lower priority):
- Fix phyllotaxis fan artifact (increase min_loop_index)
- Pinnate venation (stronger midrib + lateral branching)
- Petiole (leaf stalk cylinder)
- Seasonal palette presets in config

---

## COORDINATE SYSTEM
- Y-up, -Z into scene
- Camera at [0, 0, 16] looking at [0, 2.0, 0], FOV 70

---

## GIT COMMIT DISCIPLINE
- Commit after structural changes
- Commit at stable milestones
- Do NOT commit parameter tweaks
- foliage_N.pbrt and tree_N.pbrt are gitignored (too large)

---

## WORK SESSION CONVENTIONS
- One step at a time, confirm before proceeding
- Code in Python unless otherwise noted
- Test renders: 500x333 or 1500x1000, 128-256 samples
- Production: 5000x4000, 256 samples (52 seconds confirmed)
- Target: Epson P9000, Hahnemuhle Fine Art Baryta, 36" wide format

---

## SUPPLEMENTAL REFERENCE DOCUMENTS (in project knowledge)
1. SpaceColonizationAlgorithm_Runion.pdf
2. RunionLeafVenationPatterns.pdf
3. TheAlgorithmicBeautyOfPlants.pdf