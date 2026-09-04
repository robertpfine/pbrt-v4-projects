# Compiled cloud-grid builder

`cloud_grid_builder.cpp` is a targeted CPU accelerator for cloud density-grid
construction. It is not a second scene builder and does not read the Art Studio
configuration directly. `cloud_grid_contract.py` resolves one cloud into a
self-contained versioned JSON job and invokes the executable.

Build it from the repository root:

```bash
./build_cloud_grid_builder.sh
```

The binary is written to the gitignored path
`build/cloud_grid_builder/cloud_grid_builder`. The current configuration selects
it under `scene.sky.clouds.grid_builder`; `backend: "python"` selects the
unchanged reference implementation. With `fallback_to_python: true`, a direct
scene build can continue through the reference path if the compiled executable
cannot run.

The helper dynamically calls the native `noise._perlin` implementation already
used by Python. This preserves the established Perlin field rather than
introducing a visually different noise implementation. No Python code executes
inside the voxel loop. `threads: 0` selects the machine's available CPU thread
count; a positive value fixes the count explicitly.

Run the parity tests with:

```bash
python3 -m unittest tests.test_cloud_grid_builder -v
```

Those tests cover lobed density, mottled-veil RGB optical grids, depth slope,
depth falloff, dark undersides, fractional octaves, domain warp, and deterministic
single- versus multi-thread output. The PBRT arrays retain the existing
five-decimal serialization precision.
