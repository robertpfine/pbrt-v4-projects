#!/usr/bin/env python3
"""
build_scene.py  —  working-scene builder for PBRT-v4 Art Studio
========================================================
Reads config.json and generates two files:

  1. scene_files/volumes/rgbgrid.pbrt
     The MakeNamedMedium block containing the voxel grid
     sigma_s and sigma_a arrays. Must be Included in the
     scene before WorldBegin.

  2. scene_files/scene.pbrt
     The complete pbrt-v4 scene description, assembled
     from all enabled objects in config.json.

Usage:
  python3 build_scene.py                        # looks for config.json in same directory
  python3 build_scene.py path/to/config.json    # explicit config path (used by render_pipeline.sh)
========================================================
"""

import os
import sys
import json
import math
import random
import subprocess
import time
from pathlib import Path
from noise import pnoise2, pnoise3

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, REPOSITORY_ROOT)

from phyllotaxis import area_dome_points, dome_height, vogel_points
from clouds import create_clouds
from cloud_grid_contract import (
    normalized_cloud_job,
    run_compiled_builder,
    write_job,
)
from rain import create_rain_curtains
from distant_hills import (
    create_distant_hill_grass,
    create_distant_hill_scatter,
    create_distant_hills,
    create_horizon_tree_line,
    flatten_triplets,
)
from fractal_tree import fractal_tree
from lsystem import christmas_tree, live_oak
from terrain_surface_texture import generate_terrain_surface_maps
from vista_surface_texture import generate_vista_surface_mottle
from terrain import create_terrain
from terrain_details import alignment_rotation, scatter_points, spatial_direction_offset


# ==============================================================
# SECTION 1 — UTILITY FUNCTIONS
# ==============================================================

def fmt_floats(values, per_line=9):
    """
    Format a flat list of floats into indented rows of per_line values.
    Used to write the sigma_s and sigma_a arrays inside MakeNamedMedium.

    Input:  flat list of floats
    Output: multi-line string, each line indented 8 spaces
    """
    lines = []
    for i in range(0, len(values), per_line):
        chunk = values[i:i + per_line]
        lines.append("        " + " ".join(f"{v:.5f}" for v in chunk))
    return "\n".join(lines)


# ==============================================================
# SECTION 2 — WAVELENGTH TO RGB
# ==============================================================

def wavelength_to_rgb(wl):
    """
    Convert a visible-spectrum wavelength (nm) to an approximate RGB triple.
    Range: 380–700 nm. Values outside this range return (0, 0, 0).

    Uses a standard piecewise linear approximation with
    perceptual brightness falloff at the spectral extremes.

    Config usage: zone["wavelength"] in the "zones" array.

    Input:  wl  — wavelength in nanometers (float or int)
    Output: (r, g, b) tuple, each component in [0.0, 1.0]
    """
    r, g, b = 0.0, 0.0, 0.0

    if   380 <= wl < 440:
        r = -(wl - 440) / (440 - 380)
        b = 1.0
    elif 440 <= wl < 490:
        g = (wl - 440) / (490 - 440)
        b = 1.0
    elif 490 <= wl < 510:
        g = 1.0
        b = -(wl - 510) / (510 - 490)
    elif 510 <= wl < 580:
        r = (wl - 510) / (580 - 510)
        g = 1.0
    elif 580 <= wl < 645:
        r = 1.0
        g = -(wl - 645) / (645 - 580)
    elif 645 <= wl <= 700:
        r = 1.0

    # Perceptual brightness falloff at violet and deep red extremes
    if   380 <= wl < 420:
        factor = 0.3 + 0.7 * (wl - 380) / (420 - 380)
    elif 645 < wl <= 700:
        factor = 0.3 + 0.7 * (700 - wl) / (700 - 645)
    else:
        factor = 1.0

    return (r * factor, g * factor, b * factor)


# ==============================================================
# SECTION 3 — RGBGRID VOXEL COMPUTATION
# ==============================================================

def compute_rgbgrid(grid_cfg, zones):
    """
    Build the sigma_s and sigma_a voxel arrays for the rgbgrid medium.

    Each voxel gets an RGB sigma_s value computed by summing the
    contributions of all enabled zones. Each zone is a colored band
    defined by position, wavelength, width, and strength. Zone
    influence falls off linearly with distance from the zone center
    (tent function).

    sigma_a is spatially uniform — the same value in every voxel,
    taken from grid_cfg["sigma_a"].

    Config reads:
      grid_cfg — scene.grid  (nx, ny, nz, axis, sigma_a, world_min, world_max)
      zones    — scene.zones (position, wavelength, width, strength, enabled)

    Output:
      sigma_s      — flat list of floats, length nx*ny*nz*3 (RGB interleaved)
      sigma_a_flat — flat list of floats, length nx*ny*nz*3 (uniform RGB)

    Voxel iteration order: Z outer, Y middle, X inner (pbrt rgbgrid convention).
    Axis parameter controls which axis the zone positions are mapped along.
    """
    nx, ny, nz  = grid_cfg["nx"], grid_cfg["ny"], grid_cfg["nz"]
    axis        = grid_cfg["axis"]       # "X", "Y", or "Z"
    sigma_a_val = grid_cfg["sigma_a"]    # uniform absorption coefficient

    sigma_s      = []
    sigma_a_flat = []
    le_flat      = []

    for k in range(nz):
        for j in range(ny):
            for i in range(nx):

                # Normalized position along the chosen axis [0.0, 1.0]
                if   axis == "X": t = (i + 0.5) / nx
                elif axis == "Y": t = (j + 0.5) / ny
                else:             t = (k + 0.5) / nz

                # Noise modulation
                noise_cfg = grid_cfg.get("noise", {})
                noise_enabled = noise_cfg.get("enabled", False)
                mode = noise_cfg.get("mode", "position")

                if noise_enabled:
                    pos_cfg = noise_cfg.get("position", {})
                    den_cfg = noise_cfg.get("density", {})

                    if mode in ("position", "both"):
                        pf = pos_cfg.get("frequency", 0.5)
                        n_pos = pnoise3(
                            i * pf / nx, j * pf / ny, k * pf / nz,
                            octaves     = pos_cfg.get("octaves",     4),
                            persistence = pos_cfg.get("persistence", 0.5),
                            lacunarity  = pos_cfg.get("lacunarity",  2.0)
                        )
                    else:
                        n_pos = 0.0

                    if mode in ("density", "both"):
                        df = den_cfg.get("frequency", 2.0)
                        n_den = pnoise3(
                            i * df / nx, j * df / ny, k * df / nz,
                            octaves     = den_cfg.get("octaves",     6),
                            persistence = den_cfg.get("persistence", 0.6),
                            lacunarity  = den_cfg.get("lacunarity",  2.0)
                        )
                    else:
                        n_den = 0.0
                else:
                    n_pos = 0.0
                    n_den = 0.0

                # Accumulate RGB scattering from all enabled zones
                sr = sg = sb = 0.0
                for zone in zones:
                    if not zone.get("enabled", True):
                        continue

                    # Position shift
                    pos_amp = noise_cfg.get("position", {}).get("amplitude", 0.15)
                    t_shifted = t + n_pos * pos_amp if noise_enabled else t
                    d = abs(t_shifted - zone["position"])
                    w = max(0.0, 1.0 - d / zone["width"])

                    # Density modulation
                    den_amp = noise_cfg.get("density", {}).get("amplitude", 0.8)
                    density_scale = 1.0 + n_den * den_amp if noise_enabled else 1.0
                    density_scale = max(0.0, density_scale)

                    rgb = wavelength_to_rgb(zone["wavelength"])
                    sr += w * zone["strength"] * density_scale * rgb[0]
                    sg += w * zone["strength"] * density_scale * rgb[1]
                    sb += w * zone["strength"] * density_scale * rgb[2]

                sigma_s      += [sr, sg, sb]
                sigma_a_flat += [sigma_a_val, sigma_a_val, sigma_a_val]
                le_flat      += [sr, sg, sb]

    return sigma_s, sigma_a_flat, le_flat


# ==============================================================
# SECTION 4 — WRITE MEDIUM FILE (scene_files/volumes/rgbgrid.pbrt)
# ==============================================================

def write_fog_medium(cfg, lines):
    """
    Write a homogeneous fog medium named "fog" into the world section.
    This creates the exterior atmospheric medium that makes god rays visible.
    Config reads: scene.fog (enabled, sigma_a, sigma_s, g, camera_inside)

    pbrt note: MakeNamedMedium for homogeneous media can appear inside
    the world section, unlike rgbgrid which uses Include.
    """
    fog = cfg["scene"].get("fog")
    if not fog or not fog.get("enabled", True):
        return

    camera_medium = "fog" if fog.get("camera_inside", True) else ""

    noise = fog.get("noise", {})
    lines.append('MakeNamedMedium "fog"')
    if noise.get("enabled", False):
        resolution = noise.get("resolution", [48, 36, 48])
        nx, ny, nz = (int(resolution[0]), int(resolution[1]), int(resolution[2]))
        bounds_min = noise.get("bounds_min", [-700.0, -500.0, -700.0])
        bounds_max = noise.get("bounds_max", [700.0, 700.0, 700.0])
        frequency = float(noise.get("frequency", 0.006))
        octaves = int(noise.get("octaves", 3))
        persistence = float(noise.get("persistence", 0.5))
        lacunarity = float(noise.get("lacunarity", 2.0))
        seed = int(noise.get("seed", 19))
        base_density = float(noise.get("base_density", 0.65))
        contrast = float(noise.get("contrast", 0.90))
        height_falloff = noise.get("height_falloff", {})
        falloff_enabled = bool(height_falloff.get("enabled", False))
        full_density_height = float(
            height_falloff.get("full_density_height", bounds_min[1])
        )
        zero_density_height = float(
            height_falloff.get("zero_density_height", bounds_max[1])
        )
        falloff_exponent = float(height_falloff.get("exponent", 1.0))
        if nx < 2 or ny < 2 or nz < 2:
            raise ValueError("fog noise resolution values must be at least 2")
        if falloff_enabled and zero_density_height <= full_density_height:
            raise ValueError(
                "fog height_falloff zero_density_height must exceed "
                "full_density_height"
            )
        if falloff_exponent <= 0.0:
            raise ValueError("fog height_falloff exponent must be positive")
        density = []
        for z_index in range(nz):
            z = bounds_min[2] + (bounds_max[2] - bounds_min[2]) * z_index / (nz - 1)
            for y_index in range(ny):
                y = bounds_min[1] + (bounds_max[1] - bounds_min[1]) * y_index / (ny - 1)
                for x_index in range(nx):
                    x = bounds_min[0] + (bounds_max[0] - bounds_min[0]) * x_index / (nx - 1)
                    value = pnoise3(
                        x * frequency, y * frequency, z * frequency,
                        octaves=octaves,
                        persistence=persistence,
                        lacunarity=lacunarity,
                        repeatx=1024, repeaty=1024, repeatz=1024,
                        base=seed,
                    )
                    local_density = max(0.0, base_density + contrast * value)
                    if falloff_enabled:
                        height_fraction = min(
                            1.0,
                            max(
                                0.0,
                                (y - full_density_height)
                                / (zero_density_height - full_density_height),
                            ),
                        )
                        smooth_height = (
                            height_fraction
                            * height_fraction
                            * (3.0 - 2.0 * height_fraction)
                        )
                        local_density *= (1.0 - smooth_height) ** falloff_exponent
                    density.append(local_density)
        lines += [
            '    "string type" [ "uniformgrid" ]',
            f'    "integer nx" [ {nx} ] "integer ny" [ {ny} ] "integer nz" [ {nz} ]',
            (
                '    "point3 p0" [ '
                f'{bounds_min[0]} {bounds_min[1]} {bounds_min[2]} ]'
            ),
            (
                '    "point3 p1" [ '
                f'{bounds_max[0]} {bounds_max[1]} {bounds_max[2]} ]'
            ),
            '    "float density" [',
            fmt_floats(density, per_line=12),
            '    ]',
        ]
    else:
        lines.append('    "string type"  [ "homogeneous" ]')
    lines += [
        f'    "rgb sigma_a" [ {fog["sigma_a"]} {fog["sigma_a"]} {fog["sigma_a"]} ]',
        f'    "rgb sigma_s" [ {fog["sigma_s"]} {fog["sigma_s"]} {fog["sigma_s"]} ]',
        f'    "float g"     [ {fog["g"]} ]',
        '',
        f'MediumInterface "" "{camera_medium}"',
        '',
    ]


def write_fog_boundary(lines, fog):
    """Write an invisible spherical boundary for a finite fog medium."""

    if not fog or not fog.get("enabled", False):
        return
    radius = float(fog.get("boundary_radius", 700.0))
    center = fog.get("boundary_center", [0.0, 100.0, 0.0])
    lines += [
        '# Finite atmospheric boundary',
        'AttributeBegin',
        f'    Translate {center[0]} {center[1]} {center[2]}',
        '    Material "interface"',
        '    MediumInterface "fog" ""',
        f'    Shape "sphere"  "float radius" [ {radius} ]',
        'AttributeEnd',
        '',
    ]


def _cloud_medium_name(index, formation):
    safe_name = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in formation.name
    )
    return f"cloud_{index}_{safe_name}"


def write_cloud_media(lines, cloud_config, scene_root):
    """Declare bounded heterogeneous media for enabled sky formations."""

    formations = create_clouds(cloud_config)
    enabled_configs = [
        item
        for item in cloud_config.get("formations", [])
        if item.get("enabled", True)
    ]
    grid_builder = cloud_config.get("grid_builder", {})
    backend = str(grid_builder.get("backend", "python"))
    if backend not in ("python", "cpp"):
        raise ValueError(f"unsupported cloud grid-builder backend: {backend!r}")
    executable = Path(REPOSITORY_ROOT) / grid_builder.get(
        "executable", "build/cloud_grid_builder/cloud_grid_builder"
    )
    threads = int(grid_builder.get("threads", 1))
    fallback = bool(grid_builder.get("fallback_to_python", True))

    for index, (formation, formation_config) in enumerate(
        zip(formations, enabled_configs)
    ):
        nx, ny, nz = formation.resolution
        optical = formation.optical
        sigma_a = optical.get("sigma_a", [0.00015, 0.00015, 0.00015])
        sigma_s = optical.get("sigma_s", [0.006, 0.006, 0.006])
        if len(sigma_a) != 3 or len(sigma_s) != 3:
            raise ValueError(f"{formation.name}: cloud sigma values require RGB triples")
        medium_name = _cloud_medium_name(index, formation)

        if backend == "cpp":
            generated_root = Path(scene_root) / "scene_files" / "cloud_grid_jobs"
            job_path = generated_root / f"{medium_name}.json"
            output_path = generated_root / f"{medium_name}.pbrt"
            job = normalized_cloud_job(cloud_config, formation_config, index)
            write_job(job, job_path)
            started = time.perf_counter()
            try:
                completed = run_compiled_builder(
                    job_path, output_path, executable, threads
                )
                elapsed = time.perf_counter() - started
                print(
                    f"  Compiled cloud grid {formation.name}: "
                    f"{nx}x{ny}x{nz} in {elapsed:.2f}s"
                )
                if completed.stderr.strip():
                    print(f"  {completed.stderr.strip()}")
                lines.extend(output_path.read_text(encoding="utf-8").splitlines())
                continue
            except (
                OSError,
                RuntimeError,
                subprocess.CalledProcessError,
            ) as error:
                if not fallback:
                    raise
                print(
                    f"  WARNING: compiled cloud grid failed for {formation.name}; "
                    f"using Python reference ({error})"
                )

        lines += [
            f'# Cloud medium: {formation.name}',
            f'MakeNamedMedium "{medium_name}"',
        ]
        if formation.underside.get("enabled", False):
            sigma_a_grid, sigma_s_grid = formation.optical_grids()
            lines += [
                '    "string type" [ "rgbgrid" ]',
                f'    "integer nx" [ {nx} ] "integer ny" [ {ny} ] "integer nz" [ {nz} ]',
                (
                    '    "point3 p0" [ '
                    f'{formation.bounds_min[0]} {formation.bounds_min[1]} {formation.bounds_min[2]} ]'
                ),
                (
                    '    "point3 p1" [ '
                    f'{formation.bounds_max[0]} {formation.bounds_max[1]} {formation.bounds_max[2]} ]'
                ),
                '    "rgb sigma_a" [',
                fmt_floats(sigma_a_grid, per_line=12),
                '    ]',
                '    "rgb sigma_s" [',
                fmt_floats(sigma_s_grid, per_line=12),
                '    ]',
            ]
        else:
            density = formation.density_grid()
            lines += [
                '    "string type" [ "uniformgrid" ]',
                f'    "integer nx" [ {nx} ] "integer ny" [ {ny} ] "integer nz" [ {nz} ]',
                (
                    '    "point3 p0" [ '
                    f'{formation.bounds_min[0]} {formation.bounds_min[1]} {formation.bounds_min[2]} ]'
                ),
                (
                    '    "point3 p1" [ '
                    f'{formation.bounds_max[0]} {formation.bounds_max[1]} {formation.bounds_max[2]} ]'
                ),
                '    "float density" [',
                fmt_floats(density, per_line=12),
                '    ]',
                f'    "rgb sigma_a" [ {sigma_a[0]} {sigma_a[1]} {sigma_a[2]} ]',
                f'    "rgb sigma_s" [ {sigma_s[0]} {sigma_s[1]} {sigma_s[2]} ]',
            ]
        lines += [
            f'    "float g" [ {float(optical.get("g", 0.2))} ]',
            '',
        ]
    return formations


def write_cloud_boundaries(lines, formations, exterior_medium=""):
    """Write invisible boxes that bind the generated cloud media."""

    indices = (
        "0 2 1  0 3 2 "
        "5 7 4  5 6 7 "
        "4 3 0  4 7 3 "
        "1 6 5  1 2 6 "
        "4 1 5  4 0 1 "
        "3 6 2  3 7 6"
    )
    for index, formation in enumerate(formations):
        x0, y0, z0 = formation.bounds_min
        x1, y1, z1 = formation.bounds_max
        points = (
            x0, y0, z0, x1, y0, z0, x1, y1, z0, x0, y1, z0,
            x0, y0, z1, x1, y0, z1, x1, y1, z1, x0, y1, z1,
        )
        lines += [
            f'# Cloud boundary: {formation.name}',
            'AttributeBegin',
            '    Material "interface"',
            (
                f'    MediumInterface "{_cloud_medium_name(index, formation)}" '
                f'"{exterior_medium}"'
            ),
            '    Shape "trianglemesh"',
            f'        "integer indices" [ {indices} ]',
            f'        "point3 P" [ {" ".join(str(value) for value in points)} ]',
            'AttributeEnd',
            '',
        ]


def _rain_medium_name(index, curtain):
    safe_name = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in curtain.name
    )
    return f"rain_{index}_{safe_name}"


def write_rain_media(lines, rain_config):
    """Declare bounded, vertically streaked rain-curtain media."""

    curtains = create_rain_curtains(rain_config)
    for index, curtain in enumerate(curtains):
        nx, ny, nz = curtain.resolution
        optical = curtain.optical
        sigma_a = optical["sigma_a"]
        sigma_s = optical["sigma_s"]
        lines += [
            f'# Rain-curtain medium: {curtain.name}',
            f'MakeNamedMedium "{_rain_medium_name(index, curtain)}"',
            '    "string type" [ "uniformgrid" ]',
            f'    "integer nx" [ {nx} ] "integer ny" [ {ny} ] "integer nz" [ {nz} ]',
            (
                '    "point3 p0" [ '
                f'{curtain.bounds_min[0]} {curtain.bounds_min[1]} {curtain.bounds_min[2]} ]'
            ),
            (
                '    "point3 p1" [ '
                f'{curtain.bounds_max[0]} {curtain.bounds_max[1]} {curtain.bounds_max[2]} ]'
            ),
            '    "float density" [',
            fmt_floats(curtain.density_grid(), per_line=12),
            '    ]',
            f'    "rgb sigma_a" [ {sigma_a[0]} {sigma_a[1]} {sigma_a[2]} ]',
            f'    "rgb sigma_s" [ {sigma_s[0]} {sigma_s[1]} {sigma_s[2]} ]',
            f'    "float g" [ {optical["g"]} ]',
            '',
        ]
    return curtains


def write_rain_boundaries(lines, curtains, exterior_medium=""):
    """Write invisible boxes that bind the rain-curtain media."""

    indices = (
        "0 2 1  0 3 2 "
        "5 7 4  5 6 7 "
        "4 3 0  4 7 3 "
        "1 6 5  1 2 6 "
        "4 1 5  4 0 1 "
        "3 6 2  3 7 6"
    )
    for index, curtain in enumerate(curtains):
        x0, y0, z0 = curtain.bounds_min
        x1, y1, z1 = curtain.bounds_max
        points = (
            x0, y0, z0, x1, y0, z0, x1, y1, z0, x0, y1, z0,
            x0, y0, z1, x1, y0, z1, x1, y1, z1, x0, y1, z1,
        )
        lines += [
            f'# Rain-curtain boundary: {curtain.name}',
            'AttributeBegin',
            '    Material "interface"',
            (
                f'    MediumInterface "{_rain_medium_name(index, curtain)}" '
                f'"{exterior_medium}"'
            ),
            '    Shape "trianglemesh"',
            f'        "integer indices" [ {indices} ]',
            f'        "point3 P" [ {" ".join(str(value) for value in points)} ]',
            'AttributeEnd',
            '',
        ]


def write_medium(cfg, scene_root):
    """
    Generate scene_files/volumes/rgbgrid.pbrt.

    This file contains a single MakeNamedMedium block named "rgb_vol".
    It must be Included in the scene file BEFORE WorldBegin — pbrt
    requires named media to be declared in the pre-world section.

    Config reads:
      scene.grid            — grid dimensions, bounds, sigma_a
      scene.zones           — spectral zone definitions
      scene.generated_medium — output path (relative to working-scene root)

    Output file: the MakeNamedMedium "rgb_vol" block with
                 fully expanded sigma_s and sigma_a arrays.

    Returns: the relative path string (for use as the Include argument
             in the scene file).
    """
    scene  = cfg["scene"]
    g_cfg  = scene["grid"]
    if not g_cfg.get("enabled", True):
        print("  Grid disabled — skipping rgbgrid generation.")
        return None
    zones  = scene["zones"]
    out    = os.path.join(scene_root, scene["generated_medium"])

    print(f"  Building {g_cfg['nx']}x{g_cfg['ny']}x{g_cfg['nz']} rgbgrid "
          f"(axis={g_cfg['axis']}, sigma_a={g_cfg['sigma_a']})...")

    sigma_s, sigma_a_flat, le_flat = compute_rgbgrid(g_cfg, zones)

    emission_cfg = g_cfg.get("emission", {})
    emission_enabled = emission_cfg.get("enabled", False)
    le_scale = emission_cfg.get("le_scale", 1.0)

    le_block = (
        f'    "float Lescale" [ {le_scale} ]\n'
        f'    "rgb Le"   [\n'
        f'{fmt_floats(le_flat)}\n'
        f'    ]\n'
    ) if emission_enabled else ""

    content = (
        f'MakeNamedMedium "rgb_vol"\n'
        f'    "string type"   [ "rgbgrid" ]\n'
        f'    "integer nx"    [ {g_cfg["nx"]} ]\n'
        f'    "integer ny"    [ {g_cfg["ny"]} ]\n'
        f'    "integer nz"    [ {g_cfg["nz"]} ]\n'
        f'    "point3 p0"     [ {g_cfg["world_min"][0]} {g_cfg["world_min"][1]} {g_cfg["world_min"][2]} ]\n'
        f'    "point3 p1"     [ {g_cfg["world_max"][0]} {g_cfg["world_max"][1]} {g_cfg["world_max"][2]} ]\n'
        f'    "float g"       [ 0.0 ]\n'
        f'    "rgb sigma_a"   [\n'
        f'{fmt_floats(sigma_a_flat)}\n'
        f'    ]\n'
        f'    "rgb sigma_s"   [\n'
        f'{fmt_floats(sigma_s)}\n'
        f'    ]\n'
        f'{le_block}'
    )

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(content)
    print(f"  Written: {out}")

    return scene["generated_medium"]   # relative path for Include directive


# ==============================================================
# SECTION 5 — SCENE BLOCK WRITERS
# Each function writes one logical section of the pbrt scene.
# They append pbrt-syntax lines to the shared `lines` list.
# ==============================================================

def write_header(lines, scene_name):
    """
    Write the comment header at the top of scene.pbrt.
    Config reads: scene.name
    """
    lines += [
        "# FILE: scene.pbrt",
        f"# SCENE: {scene_name}",
        "",
    ]


def write_camera(lines, cam):
    """
    Write LookAt and Camera directives.
    These must appear before Sampler, Integrator, and Film.
    Config reads: scene.camera (enabled, look_at, fov)

    pbrt note: LookAt takes eye / look-at point / up-vector,
               all as flat space-separated values on one line.
    """
    if not cam.get("enabled", True):
        return

    e = cam["look_at"]["eye"]
    l = cam["look_at"]["look"]
    u = cam["look_at"]["up"]

    lines += [
        f"LookAt  {e[0]} {e[1]} {e[2]}",
        f"        {l[0]} {l[1]} {l[2]}",
        f"        {u[0]} {u[1]} {u[2]}",
        "",
        f'Camera "perspective"  "float fov" [ {cam["fov"]} ]',
        "",
    ]


def write_sampler(lines, samp):
    """
    Write the Sampler directive.
    Config reads: scene.sampler (enabled, type, pixel_samples)
    """
    if not samp.get("enabled", True):
        return
    lines.append(f'Sampler "{samp["type"]}"  "integer pixelsamples" [ {samp["pixel_samples"]} ]')


def write_integrator(lines, intg):
    """
    Write the Integrator directive.
    Must be "volpath" for any scene containing a participating medium.
    Config reads: scene.integrator (enabled, type, max_depth)
    """
    if not intg.get("enabled", True):
        return
    lines.append(f'Integrator "{intg["type"]}"  "integer maxdepth" [ {intg["max_depth"]} ]')


def write_film(lines, film, output_filename):
    """
    Write the Film directive.
    Config reads: scene.film (enabled, x_resolution, y_resolution)
                  scene.output_filename
    """
    if not film.get("enabled", True):
        return
    lines += [
        f'Film "rgb"',
        f'     "string filename"     [ "{output_filename}" ]',
        f'     "integer xresolution" [ {film["x_resolution"]} ]',
        f'     "integer yresolution" [ {film["y_resolution"]} ]',
        "",
    ]


def write_medium_include(lines, medium_rel_path):
    """
    Write the Include directive for the generated rgbgrid medium file.

    IMPORTANT: This Include must appear AFTER WorldBegin.
    Despite containing a MakeNamedMedium declaration, pbrt-v4
    correctly handles medium Includes inside the world section.

    Input: medium_rel_path — path relative to the working-scene root,
                             as returned by write_medium().
    """
    lines += [
        f'Include "{medium_rel_path}"',
        "",
    ]


def write_lights(lines, lights):
    """
    Write all enabled LightSource directives.
    Must appear after WorldBegin.
    Config reads: scene.lights[] (enabled, type, color_mode, temperature/color,
                                 scale, position)

    Supported light types:
      "infinite" — environment/sky light, no position
      "point"    — point light at a world-space position

    Supported color modes:
      "blackbody" — color temperature in Kelvin (physically based)
      "rgb"       — explicit RGB color triplet
    """
    for light in lights:
        if not light.get("enabled", True):
            continue

        ltype = light["type"]
        mode  = light["color_mode"]
        color = light.get("color", light.get("temperature"))
        if isinstance(color, list):
            color = " ".join(str(component) for component in color)
        scale = light["scale"]

        if ltype == "infinite":
            lines.append(
                f'LightSource "infinite"'
                f'  "{mode} L" [ {color} ]'
                f'  "float scale" [ {scale} ]'
            )

        elif ltype == "point":
            p = light["position"]
            lines.append(
                f'LightSource "point"'
                f'  "point3 from" [ {p[0]} {p[1]} {p[2]} ]'
                f'  "{mode} I" [ {color} ]'
                f'  "float scale" [ {scale} ]'
            )
 
    
        elif ltype == "spot":
            p = light["position"]
            l = light["look_at"]
            lines.append(
                f'LightSource "spot"'
                f'  "point3 from" [ {p[0]} {p[1]} {p[2]} ]'
                f'  "point3 to"   [ {l[0]} {l[1]} {l[2]} ]'
                f'  "float coneangle"      [ {light["cone_angle"]} ]'
                f'  "float conedeltaangle" [ {light["cone_delta_angle"]} ]'
                f'  "{mode} I" [ {color} ]'
                f'  "float scale" [ {scale} ]'
            )
    
        elif ltype == "distant":
            f = light["from"]
            t = light["to"]
            lines.append(
                f'LightSource "distant"'
                f'  "point3 from" [ {f[0]} {f[1]} {f[2]} ]'
                f'  "point3 to"   [ {t[0]} {t[1]} {t[2]} ]'
                f'  "{mode} L" [ {color} ]'
                f'  "float scale" [ {scale} ]'
            )
    
    lines.append("")


def write_sun_aperture(lines, aperture, lights):
    """Occlude a distant light except for a finite, parallel-ray aperture."""
    if not aperture or not aperture.get("enabled", False):
        return

    light_label = aperture["light"]
    light = next(
        (item for item in lights
         if item.get("enabled", True) and item.get("label") == light_label),
        None,
    )
    if light is None:
        raise ValueError(f"sun_aperture light {light_label!r} is not enabled")
    if light.get("type") != "distant":
        raise ValueError("sun_aperture must reference a distant light")

    source = light["from"]
    target = light["to"]
    direction = [target[i] - source[i] for i in range(3)]
    magnitude = math.sqrt(sum(value * value for value in direction))
    if magnitude == 0:
        raise ValueError("distant light from and to points must differ")
    direction = [value / magnitude for value in direction]

    reference = [0.0, 1.0, 0.0]
    if abs(sum(direction[i] * reference[i] for i in range(3))) > 0.95:
        reference = [1.0, 0.0, 0.0]
    u = [
        direction[1] * reference[2] - direction[2] * reference[1],
        direction[2] * reference[0] - direction[0] * reference[2],
        direction[0] * reference[1] - direction[1] * reference[0],
    ]
    u_length = math.sqrt(sum(value * value for value in u))
    u = [value / u_length for value in u]
    v = [
        direction[1] * u[2] - direction[2] * u[1],
        direction[2] * u[0] - direction[0] * u[2],
        direction[0] * u[1] - direction[1] * u[0],
    ]

    beam_target = aperture["beam_target"]
    distance = float(aperture["mask_distance"])
    center = [beam_target[i] - direction[i] * distance for i in range(3)]
    outer_radius = float(aperture["outer_radius"])
    points = []
    indices = []
    mode = aperture.get("mode", "single")
    if mode == "cloud_breakup":
        resolution = int(aperture.get("grid_resolution", 96))
        frequency = float(aperture.get("cloud_frequency", 0.01))
        octaves = int(aperture.get("cloud_octaves", 2))
        detail_frequency = float(
            aperture.get("cloud_detail_frequency", 3.5 * frequency)
        )
        detail_strength = float(aperture.get("cloud_detail_strength", 0.35))
        threshold = float(aperture.get("open_threshold", 0.15))
        edge_softness = max(0.0, float(aperture.get("edge_softness", 0.0)))
        seed = int(aperture.get("seed", 0))
        if resolution < 2:
            raise ValueError("sun_aperture grid_resolution must be at least 2")

        for row in range(resolution + 1):
            local_v = -outer_radius + 2.0 * outer_radius * row / resolution
            for col in range(resolution + 1):
                local_u = -outer_radius + 2.0 * outer_radius * col / resolution
                points.extend(
                    center[j] + local_u * u[j] + local_v * v[j]
                    for j in range(3)
                )

        for row in range(resolution):
            local_v = -outer_radius + 2.0 * outer_radius * (row + 0.5) / resolution
            for col in range(resolution):
                local_u = -outer_radius + 2.0 * outer_radius * (col + 0.5) / resolution
                cloud_body = pnoise2(
                    local_u * frequency,
                    local_v * frequency,
                    octaves=octaves,
                    persistence=0.55,
                    lacunarity=2.0,
                    repeatx=4096,
                    repeaty=4096,
                    base=seed,
                )
                cloud_detail = pnoise2(
                    local_u * detail_frequency,
                    local_v * detail_frequency,
                    octaves=2,
                    persistence=0.50,
                    lacunarity=2.0,
                    repeatx=4096,
                    repeaty=4096,
                    base=seed + 97,
                )
                cloud_value = cloud_body + detail_strength * cloud_detail
                if edge_softness > 0.0:
                    transition = max(
                        0.0,
                        min(1.0, (
                            cloud_value - (threshold - edge_softness)
                        ) / (2.0 * edge_softness)),
                    )
                    transmission = transition * transition * (3.0 - 2.0 * transition)
                    cell_hash = math.sin(
                        (col + 1) * 127.1 + (row + 1) * 311.7 + seed * 74.7
                    ) * 43758.5453123
                    cell_random = cell_hash - math.floor(cell_hash)
                    is_open = cell_random < transmission
                else:
                    is_open = cloud_value > threshold
                if is_open:
                    continue
                lower_left = row * (resolution + 1) + col
                lower_right = lower_left + 1
                upper_left = lower_left + resolution + 1
                upper_right = upper_left + 1
                indices.extend([
                    lower_left, lower_right, upper_right,
                    lower_left, upper_right, upper_left,
                ])
    elif mode == "single":
        inner_radius = float(aperture["aperture_radius"])
        segments = int(aperture.get("segments", 96))
        irregularity = float(aperture.get("edge_irregularity", 0.0))
        lobes = int(aperture.get("edge_lobes", 5))
        phase = math.radians(float(aperture.get("edge_phase_degrees", 0.0)))
        if segments < 3 or inner_radius <= 0 or outer_radius <= inner_radius:
            raise ValueError("sun_aperture requires segments >= 3 and 0 < aperture_radius < outer_radius")
        for i in range(segments):
            angle = 2.0 * math.pi * i / segments
            ripple = 1.0 + irregularity * math.sin(lobes * angle + phase)
            for radius in (inner_radius * ripple, outer_radius):
                points.extend(
                    center[j] + radius * (math.cos(angle) * u[j] + math.sin(angle) * v[j])
                    for j in range(3)
                )
        for i in range(segments):
            next_i = (i + 1) % segments
            inner_i, outer_i = 2 * i, 2 * i + 1
            inner_next, outer_next = 2 * next_i, 2 * next_i + 1
            indices.extend([inner_i, outer_i, outer_next, inner_i, outer_next, inner_next])
    else:
        raise ValueError(f"unsupported sun_aperture mode {mode!r}")

    reflectance = aperture.get("reflectance", [0.001, 0.001, 0.001])
    lines += [
        "# Parallel sunlight aperture mask",
        "AttributeBegin",
        f'    Material "diffuse" "rgb reflectance" [ {" ".join(map(str, reflectance))} ]',
        '    Shape "trianglemesh"',
        f'        "point3 P" [ {" ".join(f"{value:.6g}" for value in points)} ]',
        f'        "integer indices" [ {" ".join(map(str, indices))} ]',
        "AttributeEnd",
        "",
    ]


def write_geometry(lines, geometry, scene_root=None):
    """
    Write all enabled geometry objects as AttributeBegin/AttributeEnd blocks.
    Must appear after WorldBegin.
    Config reads: scene.geometry[] (enabled, label, material, transform, medium, shape)

    Transform order within an AttributeBegin block matters in pbrt —
    transforms are applied in reverse order (last listed = first applied).
    The order here is: Translate, then Rotate — adjust per object as needed.

    MediumInterface must appear after transforms and before Shape.
    The second argument "" means no exterior medium (vacuum outside).

    Supported material types:  "diffuse", "interface"
    Supported shape types:     "sphere", "bilinearmesh"
    """
    for obj in geometry:
        if not obj.get("enabled", True):
            continue

        lines.append(f'# {obj.get("label", "geometry")}')
        lines.append("AttributeBegin")

        # --- Medium binding (after transforms, before shape) ---
        if "medium_interior" in obj or "medium_exterior" in obj:
            interior = obj.get("medium_interior", "")
            exterior = obj.get("medium_exterior", "")
            lines.append(f'    MediumInterface "{interior}" "{exterior}"')
        elif "medium" in obj:
            lines.append(f'    MediumInterface "{obj["medium"]}" ""')
        
        
        # --- Material ---
        mat = obj["material"]
        surface_mottle_enabled = False
        if mat["type"] == "diffuse":
            reflectance_scale = float(mat.get("scale", 1.0))
            if reflectance_scale < 0.0:
                raise ValueError("diffuse material scale cannot be negative")
            r = [float(value) * reflectance_scale for value in mat["reflectance"]]
            surface_mottle = mat.get("surface_mottle", {})
            surface_mottle_enabled = surface_mottle.get("enabled", False)
            if surface_mottle_enabled:
                if scene_root is None:
                    raise ValueError("surface_mottle requires a scene root")
                label = str(obj.get("label", "geometry"))
                identifier = "".join(
                    character if character.isalnum() or character == "_" else "_"
                    for character in label
                )
                texture_name = f"{identifier}_surface_mottle"
                texture_path = os.path.join(
                    scene_root,
                    "scene_files",
                    "textures",
                    f"{texture_name}.png",
                )
                generate_vista_surface_mottle(surface_mottle, r, texture_path)
                texture_relative = os.path.relpath(texture_path, scene_root)
                lines += [
                    f'    Texture "{texture_name}" "spectrum" "imagemap"',
                    f'        "string filename" [ "{texture_relative}" ]',
                    '        "string encoding" [ "sRGB" ]',
                    '        "string wrap" [ "repeat" ]',
                    '        "string filter" [ "ewa" ]',
                    '    Material "diffuse"',
                    f'        "texture reflectance" [ "{texture_name}" ]',
                ]
            else:
                lines.append(f'    Material "diffuse"  "rgb reflectance" [ {r[0]} {r[1]} {r[2]} ]')
        elif mat["type"] == "conductor":
            r = mat["reflectance"]
            roughness = mat.get("roughness", 0.0)
            lines.append(
                f'    Material "conductor"'
                f'  "rgb reflectance" [ {r[0]} {r[1]} {r[2]} ]'
                f'  "float roughness" [ {roughness} ]'
            )
        elif mat["type"] == "interface":
            # "interface" material marks the boundary of a participating medium.
            # It has no surface appearance of its own.
            lines.append('    Material "interface"')

        # --- Transforms ---
        xf = obj.get("transform", {})
        if "translate" in xf:
            t = xf["translate"]
            lines.append(f'    Translate {t[0]} {t[1]} {t[2]}')
        for rot in xf.get("rotate", []):
            a = rot["axis"]
            lines.append(f'    Rotate {rot["angle"]}  {a[0]} {a[1]} {a[2]}')

        

        # --- Shape ---
        shp = obj["shape"]
        if shp["type"] == "sphere":
            lines.append(f'    Shape "sphere"  "float radius" [ {shp["radius"]} ]')

        elif shp["type"] == "disk":
            lines.append(f'    Shape "disk"  "float radius" [ {shp["radius"]} ]')   

        elif shp["type"] == "bilinearmesh":
            idx = " ".join(str(x) for x in shp["indices"])
            pts = " ".join(str(x) for x in shp["points"])
            lines += [
                '    Shape "bilinearmesh"',
                f'        "integer indices" [ {idx} ]',
                f'        "point3 P"        [ {pts} ]',
            ]
            uv = shp.get("uv")
            if uv is None and surface_mottle_enabled:
                uv = [0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0]
            if uv is not None:
                lines.append(
                    '        "point2 uv"       [ '
                    + " ".join(str(value) for value in uv)
                    + " ]"
                )

        elif shp["type"] == "box":
            x0, x1 = shp["x_min"], shp["x_max"]
            y0, y1 = shp["y_min"], shp["y_max"]
            z0, z1 = shp["z_min"], shp["z_max"]

            # 8 corners of the box
            # 0: x0 y0 z0,  1: x1 y0 z0,  2: x1 y1 z0,  3: x0 y1 z0
            # 4: x0 y0 z1,  5: x1 y0 z1,  6: x1 y1 z1,  7: x0 y1 z1
            pts_list = [
                x0, y0, z0,  x1, y0, z0,  x1, y1, z0,  x0, y1, z0,
                x0, y0, z1,  x1, y0, z1,  x1, y1, z1,  x0, y1, z1
            ]
            pts = "  ".join(str(v) for v in pts_list)

            # 6 faces, each as 2 triangles (12 triangles total)
            # Winding order: normals point inward (into the medium)
            idx = (
                "0 2 1  0 3 2 "   # front face
                "5 7 4  5 6 7 "   # back face
                "4 3 0  4 7 3 "   # left face
                "1 6 5  1 2 6 "   # right face
                "4 1 5  4 0 1 "   # bottom face
                "3 6 2  3 7 6"    # top face
            )

            lines += [
                '    Shape "trianglemesh"',
                f'        "integer indices" [ {idx} ]',
                f'        "point3 P"        [ {pts} ]',
            ]


        lines.append("AttributeEnd")
        lines.append("")


def write_phyllotaxis_organ(lines, object_name, organ):
    """Define one reusable PBRT-v4 organ for a phyllotactic zone."""

    shape = organ.get("shape", "sphere")
    material = organ.get("material", {})
    reflectance = material.get("reflectance", [0.15, 0.08, 0.02])
    if len(reflectance) != 3:
        raise ValueError("phyllotaxis reflectance must contain three values")

    lines += [
        f'ObjectBegin "{object_name}"',
        (
            '    Material "diffuse"  "rgb reflectance" '
            f'[ {reflectance[0]} {reflectance[1]} {reflectance[2]} ]'
        ),
    ]

    if shape in ("sphere", "disk"):
        radius = float(organ.get("radius", 0.45))
        if radius <= 0:
            raise ValueError("phyllotaxis organ radius must be positive")
        if shape == "sphere":
            lines.append(f'    Shape "sphere"  "float radius" [ {radius} ]')
        else:
            lines += [
                '    Rotate 90 1 0 0',
                f'    Shape "disk"  "float radius" [ {radius} ]',
            ]
    elif shape == "cone":
        radius = float(organ.get("radius", 0.45))
        height = float(organ.get("height", 0.9))
        if radius <= 0 or height <= 0:
            raise ValueError("cone radius and height must be positive")
        lines += [
            '    Rotate -90 1 0 0',
            (
                '    Shape "cone"'
                f'  "float radius" [ {radius} ]'
                f'  "float height" [ {height} ]'
            ),
        ]
    elif shape == "ellipsoid":
        radius = float(organ.get("radius", 0.45))
        height = float(organ.get("height", 0.8))
        if radius <= 0 or height <= 0:
            raise ValueError("ellipsoid radius and height must be positive")
        lines += [
            f'    Scale {radius} {height} {radius}',
            '    Shape "sphere"  "float radius" [ 1 ]',
        ]
    elif shape == "seed":
        radius = float(organ.get("radius", 0.55))
        height = float(organ.get("height", 1.3))
        length_segments = int(organ.get("segments", 10))
        radial_segments = int(organ.get("radial_segments", 10))
        if radius <= 0 or height <= 0:
            raise ValueError("seed radius and height must be positive")
        if length_segments < 4 or radial_segments < 4:
            raise ValueError("seed mesh resolution is too low")

        vertices = []
        indices = []
        for segment in range(length_segments + 1):
            t = segment / length_segments
            # Narrow attachment, full shoulder, then a pointed distal end.
            profile = math.sin(math.pi * t) ** 0.88
            profile *= 0.76 + 0.28 * t
            profile *= 1.0 - 0.12 * t * t
            ring_radius = radius * profile
            y = height * t
            for side in range(radial_segments):
                angle = 2.0 * math.pi * side / radial_segments
                vertices += [
                    ring_radius * math.cos(angle),
                    y,
                    ring_radius * math.sin(angle),
                ]
        for segment in range(length_segments):
            ring0 = segment * radial_segments
            ring1 = (segment + 1) * radial_segments
            for side in range(radial_segments):
                next_side = (side + 1) % radial_segments
                indices += [
                    ring0 + side, ring0 + next_side, ring1 + side,
                    ring0 + next_side, ring1 + next_side, ring1 + side,
                ]
        points = " ".join(f"{value:.8f}" for value in vertices)
        index_values = " ".join(str(value) for value in indices)
        lines += [
            '    Shape "trianglemesh"',
            f'        "integer indices" [ {index_values} ]',
            f'        "point3 P" [ {points} ]',
        ]
    elif shape == "ray_floret":
        radius = float(organ.get("radius", 0.68))
        height = float(organ.get("height", 0.9))
        length_segments = int(organ.get("segments", 7))
        radial_segments = int(organ.get("radial_segments", 12))
        lobes = int(organ.get("lobes", 5))
        lobe_depth = float(organ.get("lobe_depth", 0.18))
        if radius <= 0 or height <= 0 or lobes < 3:
            raise ValueError("invalid ray floret dimensions")

        vertices = []
        indices = []
        for segment in range(length_segments + 1):
            t = segment / length_segments
            # An open tubular corolla: narrow at its attachment, widening
            # toward a strongly five-lobed rim instead of closing as a nub.
            profile = 0.24 + 0.46 * t + 0.24 * math.sin(math.pi * t)
            y = height * t
            for side in range(radial_segments):
                angle = 2.0 * math.pi * side / radial_segments
                corrugation = 1.0 + lobe_depth * t * t * math.cos(lobes * angle)
                ring_radius = radius * profile * corrugation
                vertices += [
                    ring_radius * math.cos(angle),
                    y,
                    ring_radius * math.sin(angle),
                ]
        for segment in range(length_segments):
            ring0 = segment * radial_segments
            ring1 = (segment + 1) * radial_segments
            for side in range(radial_segments):
                next_side = (side + 1) % radial_segments
                indices += [
                    ring0 + side, ring0 + next_side, ring1 + side,
                    ring0 + next_side, ring1 + next_side, ring1 + side,
                ]
        points = " ".join(f"{value:.8f}" for value in vertices)
        index_values = " ".join(str(value) for value in indices)
        lines += [
            '    Shape "trianglemesh"',
            f'        "integer indices" [ {index_values} ]',
            f'        "point3 P" [ {points} ]',
            '    AttributeBegin',
            f'        Translate 0 {height * 0.48:.8f} 0',
            '        Rotate -90 1 0 0',
            (
                '        Shape "cone"'
                f'  "float radius" [ {radius * 0.24:.8f} ]'
                f'  "float height" [ {height * 0.82:.8f} ]'
            ),
            '    AttributeEnd',
        ]
    elif shape == "petal":
        length = float(organ.get("length", 6.0))
        width = float(organ.get("width", 2.0))
        camber = float(organ.get("camber", 0.35))
        droop = float(organ.get("droop", 0.0))
        cup = float(organ.get("cup", 0.0))
        ripple = float(organ.get("ripple", 0.0))
        twist = math.radians(float(organ.get("twist", 0.0)))
        segments = int(organ.get("segments", 10))
        if length <= 0 or width <= 0:
            raise ValueError("petal length and width must be positive")
        if segments < 3:
            raise ValueError("petal segments must be at least three")

        vertices = []
        normals = []
        indices = []
        for segment in range(segments + 1):
            t = segment / segments
            x = length * t
            width_profile = math.sin(math.pi * t) ** 0.65
            if segment == 0:
                width_profile = 0.16
            elif segment == segments:
                width_profile = 0.015
            half_width = 0.5 * width * width_profile * (1.0 - 0.12 * t)
            y = camber * math.sin(math.pi * t) - droop * t * t
            dydx = (
                camber * math.pi * math.cos(math.pi * t) - 2.0 * droop * t
            ) / length
            nx, ny = -dydx, 1.0
            normal_length = math.hypot(nx, ny)
            nx, ny = nx / normal_length, ny / normal_length
            transverse_camber = cup * math.sin(math.pi * t)
            ripple_y = ripple * math.sin(3.0 * math.pi * t) * math.sin(math.pi * t)
            twist_offset = math.sin(twist * t) * half_width
            vertices += [
                x, y + ripple_y - transverse_camber, -half_width + twist_offset,
                x, y + ripple_y + transverse_camber, half_width + twist_offset,
            ]
            normals += [nx, ny, -0.12 * cup, nx, ny, 0.12 * cup]

        for segment in range(segments):
            left0 = 2 * segment
            right0 = left0 + 1
            left1 = left0 + 2
            right1 = left0 + 3
            indices += [left0, right0, left1, right0, right1, left1]

        points = " ".join(f"{value:.8f}" for value in vertices)
        normal_values = " ".join(f"{value:.8f}" for value in normals)
        index_values = " ".join(str(value) for value in indices)
        lines += [
            '    Shape "trianglemesh"',
            f'        "integer indices" [ {index_values} ]',
            f'        "point3 P" [ {points} ]',
            f'        "normal N" [ {normal_values} ]',
        ]
        vein_height = float(organ.get("vein_height", 0.0))
        if vein_height > 0:
            vein_width = float(organ.get("vein_width", width * 0.035))
            vein_color = organ.get("vein_reflectance", [
                reflectance[0] * 0.72,
                reflectance[1] * 0.72,
                reflectance[2] * 0.72,
            ])
            vein_vertices = []
            vein_indices = []
            for segment in range(segments + 1):
                t = segment / segments
                x = length * t
                profile = math.sin(math.pi * t) ** 0.65
                y = (
                    camber * math.sin(math.pi * t)
                    - droop * t * t
                    + vein_height * profile
                )
                half_ridge = vein_width * max(0.08, profile)
                vein_vertices += [x, y, -half_ridge, x, y, half_ridge]
            for segment in range(segments):
                left0 = 2 * segment
                right0 = left0 + 1
                left1 = left0 + 2
                right1 = left0 + 3
                vein_indices += [left0, right0, left1, right0, right1, left1]
            vein_points = " ".join(f"{value:.8f}" for value in vein_vertices)
            vein_index_values = " ".join(str(value) for value in vein_indices)
            lines += [
                '    AttributeBegin',
                (
                    '        Material "diffuse"  "rgb reflectance" '
                    f'[ {vein_color[0]} {vein_color[1]} {vein_color[2]} ]'
                ),
                '        Shape "trianglemesh"',
                f'            "integer indices" [ {vein_index_values} ]',
                f'            "point3 P" [ {vein_points} ]',
                '    AttributeEnd',
            ]
    else:
        raise ValueError(f"Unsupported phyllotaxis organ shape: {shape}")

    lines += ['ObjectEnd', '']


def write_oriented_cylinder(lines, start, end, radius, reflectance):
    """Write one PBRT cylinder aligned between arbitrary world-space points."""

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dz = end[2] - start[2]
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length <= 1e-8:
        return

    ux, uy, uz = dx / length, dy / length, dz / length
    axis_x, axis_y = -uy, ux
    axis_length = math.hypot(axis_x, axis_y)
    lines += [
        'AttributeBegin',
        (
            '    Material "diffuse"  "rgb reflectance" '
            f'[ {reflectance[0]} {reflectance[1]} {reflectance[2]} ]'
        ),
        f'    Translate {start[0]:.9f} {start[1]:.9f} {start[2]:.9f}',
    ]
    if axis_length <= 1e-8:
        angle = 0.0 if uz >= 0 else 180.0
        lines.append(f'    Rotate {angle:.9f} 1 0 0')
    else:
        angle = math.degrees(math.acos(max(-1.0, min(1.0, uz))))
        lines.append(
            f'    Rotate {angle:.9f} '
            f'{axis_x / axis_length:.9f} {axis_y / axis_length:.9f} 0'
        )
    lines += [
        (
            f'    Shape "cylinder"  "float radius" [ {radius:.9f} ] '
            f'"float zmin" [ 0 ]  "float zmax" [ {length:.9f} ]'
        ),
        'AttributeEnd',
    ]


def write_curve_segment(lines, start, end, width, reflectance):
    """Write a straight segment as a cubic PBRT curve for topology studies."""

    delta = tuple(end[axis] - start[axis] for axis in range(3))
    if math.sqrt(sum(component * component for component in delta)) <= 1e-8:
        return
    control1 = tuple(start[axis] + delta[axis] / 3.0 for axis in range(3))
    control2 = tuple(start[axis] + 2.0 * delta[axis] / 3.0 for axis in range(3))
    points = " ".join(
        f"{point[0]:.9f} {point[1]:.9f} {point[2]:.9f}"
        for point in (start, control1, control2, end)
    )
    lines += [
        'AttributeBegin',
        (
            '    Material "diffuse"  "rgb reflectance" '
            f'[ {reflectance[0]} {reflectance[1]} {reflectance[2]} ]'
        ),
        (
            f'    Shape "curve"  "point3 P" [ {points} ] '
            f'"float width" [ {width:.9f} ]  "string type" [ "cylinder" ]'
        ),
        'AttributeEnd',
    ]


def write_lsystem_leaf(lines, start, end, width, reflectance):
    """Write a simple lanceolate leaf mesh aligned to a generated shoot."""

    direction = tuple(end[axis] - start[axis] for axis in range(3))
    length = math.sqrt(sum(value * value for value in direction))
    if length <= 1e-8:
        return
    tangent = tuple(value / length for value in direction)
    side = (
        tangent[2], 0.0, -tangent[0]
    )
    side_length = math.sqrt(sum(value * value for value in side))
    if side_length <= 1e-8:
        side = (1.0, 0.0, 0.0)
    else:
        side = tuple(value / side_length for value in side)
    positions = []
    for fraction, half_width in (
        (0.0, 0.0), (0.32, width), (0.70, width * 0.72), (1.0, 0.0)
    ):
        center = tuple(
            start[axis] + direction[axis] * fraction
            for axis in range(3)
        )
        if half_width == 0.0:
            positions.append(center)
        else:
            positions.append(tuple(
                center[axis] + side[axis] * half_width
                for axis in range(3)
            ))
            positions.append(tuple(
                center[axis] - side[axis] * half_width
                for axis in range(3)
            ))
    points = " ".join(
        f"{point[0]:.9f} {point[1]:.9f} {point[2]:.9f}"
        for point in positions
    )
    indices = "0 1 2 1 3 4 1 4 2 3 5 4"
    lines += [
        'AttributeBegin',
        (
            '    Material "diffuse"  "rgb reflectance" '
            f'[ {reflectance[0]} {reflectance[1]} {reflectance[2]} ]'
        ),
        '    Shape "trianglemesh"',
        f'        "integer indices" [ {indices} ]',
        f'        "point3 P" [ {points} ]',
        'AttributeEnd',
    ]


def write_terrain(lines, terrain, config, scene_root):
    """Write a procedural terrain as one PBRT triangle mesh."""

    if terrain is None:
        return
    points, normals, indices = terrain.mesh()
    material = config.get("material", {})
    reflectance = material.get("reflectance", [0.12, 0.18, 0.055])
    surface = config.get("details", {}).get("surface", {})
    point_values = " ".join(
        f"{x:.9f} {y:.9f} {z:.9f}" for x, y, z in points
    )
    normal_values = " ".join(
        f"{x:.9f} {y:.9f} {z:.9f}" for x, y, z in normals
    )
    uv_values = " ".join(
        f"{ix / (terrain.nx - 1):.9f} {iz / (terrain.nz - 1):.9f}"
        for iz in range(terrain.nz)
        for ix in range(terrain.nx)
    )
    index_values = " ".join(str(index) for index in indices)
    lines += [
        '# Procedural terrain',
        'AttributeBegin',
    ]
    if surface.get("enabled", False) and surface.get("mode") == "terrain_surface_texture":
        surface_texture = surface.get("terrain_surface_texture", {})
        texture_directory = os.path.join(scene_root, "scene_files", "textures")
        albedo_path, bump_path = generate_terrain_surface_maps(
            surface_texture, texture_directory
        )
        albedo_relative = os.path.relpath(albedo_path, scene_root)
        bump_relative = os.path.relpath(bump_path, scene_root)
        bump_scale = float(surface_texture.get("bump_scale", 0.012))
        lines += [
            '    Texture "terrain_surface_albedo" "spectrum" "imagemap"',
            f'        "string filename" [ "{albedo_relative}" ]',
            '        "string encoding" [ "sRGB" ]',
            '        "string wrap" [ "repeat" ]',
            '        "string filter" [ "ewa" ]',
        ]
        if bump_scale > 0.0:
            lines += [
                '    Texture "terrain_surface_bump_raw" "float" "imagemap"',
                f'        "string filename" [ "{bump_relative}" ]',
                '        "string encoding" [ "linear" ]',
                '        "string wrap" [ "repeat" ]',
                '        "string filter" [ "ewa" ]',
                '    Texture "terrain_surface_bump" "float" "scale"',
                '        "texture tex" [ "terrain_surface_bump_raw" ]',
                f'        "float scale" [ {bump_scale} ]',
                '    Material "diffuse"',
                '        "texture reflectance" [ "terrain_surface_albedo" ]',
                '        "texture displacement" [ "terrain_surface_bump" ]',
            ]
        else:
            lines += [
                '    Material "diffuse"',
                '        "texture reflectance" [ "terrain_surface_albedo" ]',
            ]
    elif surface.get("enabled", False):
        dark = surface.get("dark_reflectance", [v * 0.72 for v in reflectance])
        light = surface.get("light_reflectance", [min(1.0, v * 1.22) for v in reflectance])
        scale = 1.0 / max(1e-6, float(surface.get("color_frequency", 0.025)))
        micro_scale = 1.0 / max(1e-6, float(surface.get("micro_frequency", 0.35)))
        flow_angle = float(surface.get("flow_direction_degrees", 0.0))
        color_anisotropy = max(1.0, float(surface.get("color_anisotropy", 1.0)))
        micro_anisotropy = max(1.0, float(surface.get("micro_anisotropy", 1.0)))
        lines += [
            '    TransformBegin',
            f'        Rotate {flow_angle:.9f} 0 1 0',
            f'        Scale {scale / color_anisotropy:.9f} {scale:.9f} {scale:.9f}',
            '        Texture "terrain_color_amount" "float" "fbm"',
            f'            "integer octaves" [ {int(surface.get("color_octaves", 4))} ]',
            f'            "float roughness" [ {float(surface.get("color_roughness", 0.55))} ]',
            '    TransformEnd',
            '    Texture "terrain_dark" "spectrum" "constant"',
            f'        "rgb value" [ {dark[0]} {dark[1]} {dark[2]} ]',
            '    Texture "terrain_light" "spectrum" "constant"',
            f'        "rgb value" [ {light[0]} {light[1]} {light[2]} ]',
            '    Texture "terrain_color" "spectrum" "mix"',
            '        "texture tex1" [ "terrain_dark" ]',
            '        "texture tex2" [ "terrain_light" ]',
            '        "texture amount" [ "terrain_color_amount" ]',
            '    TransformBegin',
            f'        Rotate {flow_angle:.9f} 0 1 0',
            f'        Scale {micro_scale / micro_anisotropy:.9f} {micro_scale:.9f} {micro_scale:.9f}',
            '        Texture "terrain_micro_raw" "float" "fbm"',
            f'            "integer octaves" [ {int(surface.get("micro_octaves", 3))} ]',
            f'            "float roughness" [ {float(surface.get("micro_roughness", 0.55))} ]',
            '    TransformEnd',
            '    Texture "terrain_micro" "float" "scale"',
            '        "texture tex" [ "terrain_micro_raw" ]',
            f'        "float scale" [ {float(surface.get("micro_amplitude", 0.08))} ]',
        ]
        fiber_strength = float(surface.get("fiber_strength", 0.0))
        if fiber_strength > 0.0:
            fiber = surface.get("fiber_reflectance", light)
            fiber_scale = 1.0 / max(
                1e-6, float(surface.get("fiber_frequency", 1.0))
            )
            fiber_anisotropy = max(
                1.0, float(surface.get("fiber_anisotropy", 8.0))
            )
            lines += [
                '    TransformBegin',
                f'        Rotate {flow_angle:.9f} 0 1 0',
                f'        Scale {fiber_scale / fiber_anisotropy:.9f} {fiber_scale:.9f} {fiber_scale:.9f}',
                '        Texture "terrain_fiber_raw" "float" "fbm"',
                f'            "integer octaves" [ {int(surface.get("fiber_octaves", 2))} ]',
                f'            "float roughness" [ {float(surface.get("fiber_roughness", 0.45))} ]',
                '    TransformEnd',
                '    Texture "terrain_fiber_amount" "float" "scale"',
                '        "texture tex" [ "terrain_fiber_raw" ]',
                f'        "float scale" [ {fiber_strength} ]',
                '    Texture "terrain_fiber" "spectrum" "constant"',
                f'        "rgb value" [ {fiber[0]} {fiber[1]} {fiber[2]} ]',
                '    Texture "terrain_surface_color" "spectrum" "mix"',
                '        "texture tex1" [ "terrain_color" ]',
                '        "texture tex2" [ "terrain_fiber" ]',
                '        "texture amount" [ "terrain_fiber_amount" ]',
            ]
            terrain_color = "terrain_surface_color"
        else:
            terrain_color = "terrain_color"
        lines += [
            '    Material "diffuse"',
            f'        "texture reflectance" [ "{terrain_color}" ]',
            '        "texture displacement" [ "terrain_micro" ]',
        ]
    else:
        lines.append(
            '    Material "diffuse"  "rgb reflectance" '
            f'[ {reflectance[0]} {reflectance[1]} {reflectance[2]} ]'
        )
    lines += [
        '    Shape "trianglemesh"',
        f'        "integer indices" [ {index_values} ]',
        f'        "point3 P" [ {point_values} ]',
        f'        "normal N" [ {normal_values} ]',
        f'        "point2 uv" [ {uv_values} ]',
        'AttributeEnd',
        '',
    ]


def write_distant_hills(lines, config, grass_config=None, poppy_config=None):
    """Write independently designed receding-horizon terrain bands."""

    hills = create_distant_hills(config)
    if not hills:
        return
    lines += [
        '# Distant hill terrain bands',
        '',
    ]
    for index, hill in enumerate(hills):
        points, normals, indices = hill.mesh()
        reflectance = hill.reflectance
        lines += [
            f'# Distant hill layer {index + 1}: {hill.name}',
            'AttributeBegin',
            (
                '    Material "diffuse"  "rgb reflectance" '
                f'[ {reflectance[0]} {reflectance[1]} {reflectance[2]} ]'
            ),
            '    Shape "trianglemesh"',
            f'        "integer indices" [ {" ".join(str(value) for value in indices)} ]',
            f'        "point3 P" [ {flatten_triplets(points)} ]',
            f'        "normal N" [ {flatten_triplets(normals)} ]',
            'AttributeEnd',
            '',
        ]

    grass_config = grass_config or {}
    extension = grass_config.get("extension", {})
    if extension.get("enabled", False):
        target_name = str(extension.get("target_distant_hill", ""))
        target = next((hill for hill in hills if hill.name == target_name), None)
        if target is None:
            raise ValueError(
                f"grass extension references inactive distant hill {target_name!r}"
            )
        style = {
            key: value
            for key, value in grass_config.items()
            if key not in ("camera_frustum", "extension", "layers", "region")
        }
        style.update(extension)
        colors = style.get("reflectance_variants", [[0.08, 0.22, 0.035]])
        variants = max(1, int(style.get("variants", len(colors))))
        for variant in range(variants):
            points, indices = _grass_mesh(variant, style)
            color = colors[variant % len(colors)]
            lines += [
                f'ObjectBegin "distant_grass_{variant}"',
                (
                    '    Material "diffuse" "rgb reflectance" '
                    f'[ {color[0]} {color[1]} {color[2]} ]'
                ),
            ]
            _write_detail_mesh(lines, points, indices)
            lines += ['ObjectEnd', '']
        grass_points = create_distant_hill_grass(target, style)
        lines.append(
            f'# Distant grass on {target.name}: {len(grass_points)} instances'
        )
        for point in grass_points:
            angle, axis = alignment_rotation(point.normal)
            sx = point.scale * point.aspect[0]
            sy = point.scale * point.aspect[1]
            sz = point.scale * point.aspect[2]
            lines += [
                'AttributeBegin',
                (
                    f'    Translate {point.position[0]:.7f} '
                    f'{point.position[1]:.7f} {point.position[2]:.7f}'
                ),
                f'    Rotate {angle:.7f} {axis[0]:.7f} {axis[1]:.7f} {axis[2]:.7f}',
                f'    Rotate {point.rotation:.7f} 0 1 0',
                f'    Scale {sx:.7f} {sy:.7f} {sz:.7f}',
                f'    ObjectInstance "distant_grass_{point.variant}"',
                'AttributeEnd',
            ]
        lines.append('')

    poppy_config = poppy_config or {}
    extension = poppy_config.get("extension", {})
    if extension.get("enabled", False):
        target_name = str(extension.get("target_distant_hill", ""))
        target = next((hill for hill in hills if hill.name == target_name), None)
        if target is None:
            raise ValueError(
                f"poppy extension references inactive distant hill {target_name!r}"
            )
        style = {
            key: value
            for key, value in poppy_config.items()
            if key not in ("camera_frustum", "extension", "region")
        }
        style.update(extension)
        poppy_points = create_distant_hill_scatter(target, style)
        lines.append(
            f'# Distant poppies on {target.name}: {len(poppy_points)} instances'
        )
        for point in poppy_points:
            angle, axis = alignment_rotation(point.normal)
            sx = point.scale * point.aspect[0]
            sy = point.scale * point.aspect[1]
            sz = point.scale * point.aspect[2]
            lines += [
                'AttributeBegin',
                (
                    f'    Translate {point.position[0]:.7f} '
                    f'{point.position[1]:.7f} {point.position[2]:.7f}'
                ),
                f'    Rotate {angle:.7f} {axis[0]:.7f} {axis[1]:.7f} {axis[2]:.7f}',
                f'    Rotate {point.rotation:.7f} 0 1 0',
                f'    Scale {sx:.7f} {sy:.7f} {sz:.7f}',
                f'    ObjectInstance "terrain_poppies_{point.variant}"',
                'AttributeEnd',
            ]
        lines.append('')

    tree_line = config.get("tree_line", {})
    trees = create_horizon_tree_line(config, hills)
    if not trees:
        return
    reflectances = tree_line.get(
        "reflectance_variants", [[0.08, 0.10, 0.08]]
    )
    evergreen_reflectances = tree_line.get(
        "evergreen_reflectance_variants", reflectances
    )
    lines += [
        '# Sparse distant tree line',
        '',
    ]
    for variant, reflectance in enumerate(reflectances):
        lines += [
            f'ObjectBegin "distant_tree_crown_{variant}"',
            (
                '    Material "diffuse"  "rgb reflectance" '
                f'[ {reflectance[0]} {reflectance[1]} {reflectance[2]} ]'
            ),
            '    Shape "sphere"  "float radius" [ 1 ]',
            'ObjectEnd',
            '',
        ]
    for variant, reflectance in enumerate(evergreen_reflectances):
        lines += [
            f'ObjectBegin "distant_tree_evergreen_{variant}"',
            (
                '    Material "diffuse"  "rgb reflectance" '
                f'[ {reflectance[0]} {reflectance[1]} {reflectance[2]} ]'
            ),
            '    Shape "sphere"  "float radius" [ 1 ]',
            'ObjectEnd',
            '',
        ]
    crown_lobes = max(1, int(tree_line.get("crown_lobes", 1)))
    for tree_index, tree in enumerate(trees):
        x, y, z = tree.position
        radius = tree.crown_radius
        height = tree.height
        if tree.form == "evergreen":
            lobes = [
                (0.0, 0.24, 0.0, 1.00, 0.15, 1.00),
                (0.0, 0.42, 0.0, 0.76, 0.14, 0.76),
                (0.0, 0.59, 0.0, 0.52, 0.13, 0.52),
                (0.0, 0.75, 0.0, 0.27, 0.12, 0.27),
            ]
            object_name = f'distant_tree_evergreen_{tree.variant}'
        else:
            handedness = -1.0 if tree_index % 2 else 1.0
            lobes = [
                (0.0, 0.50, 0.0, 1.00, 0.50, 1.00),
                (-0.48, 0.39, 0.08, 0.72, 0.34, 0.78),
                (0.47, 0.42, -0.10, 0.76, 0.36, 0.72),
                (0.08 * handedness, 0.72, 0.04, 0.62, 0.30, 0.66),
            ]
            object_name = f'distant_tree_crown_{tree.variant}'
        for offset_x, offset_y, offset_z, scale_x, scale_y, scale_z in lobes[:crown_lobes]:
            lines += [
                'AttributeBegin',
                (
                    f'    Translate {x + offset_x * radius:.9f} '
                    f'{y + offset_y * height:.9f} '
                    f'{z + offset_z * radius:.9f}'
                ),
                (
                    f'    Scale {scale_x * radius:.9f} '
                    f'{scale_y * height:.9f} {scale_z * radius:.9f}'
                ),
                f'    ObjectInstance "{object_name}"',
                'AttributeEnd',
            ]
    lines.append('')


def _write_detail_mesh(lines, points, indices, normals=None):
    point_values = " ".join(f"{x:.6f} {y:.6f} {z:.6f}" for x, y, z in points)
    index_values = " ".join(str(value) for value in indices)
    lines += [
        '    Shape "trianglemesh"',
        f'        "integer indices" [ {index_values} ]',
        f'        "point3 P" [ {point_values} ]',
    ]
    if normals is not None:
        normal_values = " ".join(
            f"{x:.6f} {y:.6f} {z:.6f}" for x, y, z in normals
        )
        lines.append(f'        "normal N" [ {normal_values} ]')


def _grass_range(config, name, default):
    """Return a validated two-number range from a grass config block."""

    value = config.get(name, default)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"grass {name} must be a two-number array")
    low, high = float(value[0]), float(value[1])
    if low > high:
        raise ValueError(f"grass {name} minimum must not exceed its maximum")
    return low, high


def _grass_mesh(variant=0, config=None):
    """Return a configurable tuft of tapered, segmented grass-blade ribbons."""

    config = config or {}
    blade_config = config.get("blade", {})
    tuft_config = config.get("tuft", {})
    blade_count = int(tuft_config.get("blades", 7))
    segments = int(blade_config.get("segments", 3))
    if blade_count < 1:
        raise ValueError("grass tuft blades must be at least one")
    if segments < 1:
        raise ValueError("grass blade segments must be at least one")

    height_range = _grass_range(blade_config, "height", [0.82, 1.18])
    width_range = _grass_range(blade_config, "width", [0.025, 0.050])
    lean_range = _grass_range(blade_config, "lean", [0.10, 0.28])
    bend_range = _grass_range(blade_config, "bend", [-0.055, 0.055])
    droop_range = _grass_range(blade_config, "tip_droop", [0.0, 0.0])
    radius_range = _grass_range(tuft_config, "radius", [0.025, 0.14])
    tropism_config = blade_config.get("tropism", {})
    tropism_enabled = bool(tropism_config.get("enabled", False))
    tropism_range = _grass_range(tropism_config, "strength", [0.0, 0.0])
    tropism_variation = math.radians(
        float(tropism_config.get("direction_variation_degrees", 0.0))
    )
    tropism_exponent = float(tropism_config.get("curvature_exponent", 2.0))
    bend_exponent = float(blade_config.get("bend_exponent", 1.45))
    taper_exponent = float(blade_config.get("taper_exponent", 1.35))
    angle_jitter = float(tuft_config.get("angle_jitter_degrees", 18.0))
    lean_spread = math.radians(float(blade_config.get("lean_spread_degrees", 31.5127)))
    if min(height_range) <= 0.0 or min(width_range) <= 0.0:
        raise ValueError("grass blade height and width must be positive")
    if (min(radius_range) < 0.0 or bend_exponent <= 0.0
            or taper_exponent <= 0.0 or tropism_exponent <= 0.0):
        raise ValueError("grass radius must be nonnegative and exponents must be positive")

    rng = random.Random(8101 + 977 * variant)
    points, indices = [], []
    for blade in range(blade_count):
        angle = math.radians(blade * 137.5 + rng.uniform(-angle_jitter, angle_jitter))
        radial_offset = rng.uniform(*radius_range)
        cx = radial_offset * math.cos(angle * 1.7)
        cz = radial_offset * math.sin(angle * 1.7)
        side_x, side_z = -math.sin(angle), math.cos(angle)
        lean_angle = angle + rng.uniform(-lean_spread, lean_spread)
        lean = rng.uniform(*lean_range)
        bend = rng.uniform(*bend_range)
        tropism_strength = (rng.uniform(*tropism_range)
                            if tropism_enabled else 0.0)
        tropism_angle = (rng.uniform(-tropism_variation, tropism_variation)
                         if tropism_enabled else 0.0)
        # Avoid consuming a random number when droop is disabled so the
        # original grass defaults remain byte-for-byte deterministic.
        droop = (droop_range[0] if droop_range[0] == droop_range[1]
                 else rng.uniform(*droop_range))
        height = rng.uniform(*height_range)
        width = rng.uniform(*width_range)
        base = len(points)
        # Retain the original three-segment profile exactly; taller blades can
        # use more segments for a visibly smoother arc.
        levels = ((0.0, 0.34, 0.69, 1.0) if segments == 3 else
                  tuple(segment / segments for segment in range(segments + 1)))
        for level in levels:
            taper = max(0.06, 1.0 - level ** taper_exponent)
            center_x = (
                cx
                + lean * math.cos(lean_angle) * level ** bend_exponent
                + bend * side_x * math.sin(math.pi * level)
                + tropism_strength * math.cos(tropism_angle)
                * level ** tropism_exponent
            )
            center_z = (
                cz
                + lean * math.sin(lean_angle) * level ** bend_exponent
                + bend * side_z * math.sin(math.pi * level)
                + tropism_strength * math.sin(tropism_angle)
                * level ** tropism_exponent
            )
            half_width = width * taper
            center_y = height * level - droop * level ** 3
            points += [
                (center_x - side_x * half_width, center_y,
                 center_z - side_z * half_width),
                (center_x + side_x * half_width, center_y,
                 center_z + side_z * half_width),
            ]
        for segment in range(len(levels) - 1):
            lower = base + 2 * segment
            upper = lower + 2
            indices += [lower, lower + 1, upper, lower + 1, upper + 1, upper]
    return points, indices


def _fern_mesh():
    points, indices = [], []
    for frond in range(5):
        angle = math.radians(frond * 72.0 + 12.0)
        dx, dz = math.cos(angle), math.sin(angle)
        sx, sz = -dz, dx
        for step in range(1, 6):
            t = step / 6.0
            cx, cz = dx * 0.85 * t, dz * 0.85 * t
            cy = 0.62 * math.sin(t * math.pi * 0.72)
            width = 0.19 * (1.0 - 0.65 * t)
            length = 0.18 * (1.0 - 0.45 * t)
            for sign in (-1.0, 1.0):
                base = len(points)
                points += [
                    (cx, cy, cz),
                    (cx + sign * sx * width, cy + 0.02, cz + sign * sz * width),
                    (cx + sign * sx * (width + length), cy + 0.05,
                     cz + sign * sz * (width + length)),
                ]
                indices += [base, base + 1, base + 2, base + 1, base, base + 2]
    return points, indices


def _poppy_mesh(variant=0, config=None):
    """Build a field poppy as an overlapping bowl with a detailed center."""

    config = config or {}
    tropism = config.get("tropism", {})
    main_tropism = tropism.get("main_stem", {})
    bud_tropism = tropism.get("emerging_buds", {})
    foliage_tropism = tropism.get("foliage", {})
    rng = random.Random(27103 + 613 * variant)
    stem_points, stem_indices = [], []
    foliage_points, foliage_indices = [], []
    bud_points, bud_indices = [], []
    petal_points, petal_indices, petal_base_indices, petal_rim_indices, petal_normals = [], [], [], [], []
    receptacle_points, receptacle_indices = [], []
    filament_points, filament_indices = [], []
    anther_points, anther_indices = [], []
    capsule_points, capsule_indices, capsule_normals = [], [], []
    stigma_indices = []
    stigma_tube_points, stigma_tube_indices = [], []
    stem_top = float(main_tropism.get("height", 0.765))
    main_direction = math.radians(float(main_tropism.get("direction_degrees", 32.0)))
    main_bend = float(main_tropism.get("bend", 0.145))
    lateral_sway = float(main_tropism.get("lateral_sway", 0.045))
    lean_x = main_bend * math.cos(main_direction)
    lean_z = main_bend * math.sin(main_direction)

    def stem_center(t):
        sweep = main_bend * t ** 1.55
        cross = lateral_sway * math.sin(math.pi * t) * math.sin(1.7 * math.pi * t)
        return (
            math.cos(main_direction) * sweep - math.sin(main_direction) * cross,
            stem_top * t,
            math.sin(main_direction) * sweep + math.cos(main_direction) * cross,
        )

    # A segmented, gently bowed stem with small outward hairs.
    stem_segments = 10
    half_width = 0.0035
    for facing in range(2):
        base = len(stem_points)
        for segment in range(stem_segments + 1):
            t = segment / stem_segments
            cx, _, cz = stem_center(t)
            width = half_width * (1.0 - 0.25 * t)
            if facing == 0:
                stem_points += [(cx - width, stem_top * t, cz),
                                (cx + width, stem_top * t, cz)]
            else:
                stem_points += [(cx, stem_top * t, cz - width),
                                (cx, stem_top * t, cz + width)]
        for segment in range(stem_segments):
            a = base + 2 * segment
            b, c, d = a + 1, a + 2, a + 3
            stem_indices += [a, b, c, b, d, c, c, b, a, c, d, b]
    for hair in range(22):
        t = 0.08 + 0.80 * hair / 21.0
        angle = 2.39996 * hair + 0.4 * variant
        cx, cy, cz = stem_center(t)
        radial = 0.0032
        length = 0.010 + 0.003 * (hair % 3)
        base = len(stem_points)
        stem_points += [
            (cx + radial * math.cos(angle), cy, cz + radial * math.sin(angle)),
            (cx + (radial + length) * math.cos(angle), cy + 0.003,
             cz + (radial + length) * math.sin(angle)),
            (cx + radial * math.cos(angle + 0.45), cy + 0.004,
             cz + radial * math.sin(angle + 0.45)),
        ]
        stem_indices += [base, base + 1, base + 2, base + 2, base + 1, base]

    # Strongly nodding side stems carry emerging buds.
    bud_count = int(bud_tropism.get("count", 2))
    bud_droop = float(bud_tropism.get("droop", 0.30))
    bud_reach = float(bud_tropism.get("reach", 0.28))
    bud_direction = math.radians(float(bud_tropism.get("direction_degrees", 125.0)))
    for bud_index in range(bud_count):
        attach_t = 0.34 + 0.16 * bud_index
        start_x, start_y, start_z = stem_center(attach_t)
        angle = bud_direction + bud_index * math.pi
        direction_x, direction_z = math.cos(angle), math.sin(angle)
        side_x, side_z = -direction_z, direction_x
        branch_base = len(stem_points)
        branch_segments = 12
        for segment in range(branch_segments + 1):
            t = segment / branch_segments
            horizontal = bud_reach * (0.35 * t + 0.65 * t * t)
            cx = start_x + direction_x * horizontal
            cz = start_z + direction_z * horizontal
            cy = start_y + 0.36 * t - bud_droop * t ** 3
            width = 0.0050 * (1.0 - 0.30 * t)
            stem_points += [
                (cx - side_x * width, cy, cz - side_z * width),
                (cx + side_x * width, cy, cz + side_z * width),
            ]
        for segment in range(branch_segments):
            a = branch_base + 2 * segment
            b, c, d = a + 1, a + 2, a + 3
            stem_indices += [a, b, c, b, d, c, c, b, a, c, d, b]
        end_x = start_x + direction_x * bud_reach
        end_z = start_z + direction_z * bud_reach
        end_y = start_y + 0.36 - bud_droop
        rings, segments = 6, 16
        base = len(bud_points)
        for ring in range(rings + 1):
            latitude = math.pi * ring / rings
            profile = math.sin(latitude) ** 0.72
            for segment in range(segments):
                theta = 2.0 * math.pi * segment / segments
                radius = 0.020 * profile
                bud_points.append((end_x + radius * math.cos(theta),
                                   end_y + 0.038 * math.cos(latitude),
                                   end_z + radius * math.sin(theta)))
        for ring in range(rings):
            for segment in range(segments):
                a = base + ring * segments + segment
                b = base + ring * segments + (segment + 1) % segments
                c, d = a + segments, b + segments
                bud_indices += [a, c, b, b, c, d]

    # Alternating pinnately lobed leaves follow the bowed lower stem.
    foliage_direction = math.radians(float(
        foliage_tropism.get("direction_degrees", 205.0)
    ))
    foliage_spread = float(foliage_tropism.get("spread_degrees", 115.0))
    foliage_droop = float(foliage_tropism.get("droop", 0.52))
    for leaf_index, attach_t in enumerate(
            (0.08, 0.12, 0.18, 0.25, 0.33, 0.42, 0.52, 0.63)):
        alternating = -1.0 if leaf_index % 2 else 1.0
        angle = (foliage_direction + alternating * math.radians(foliage_spread) *
                 rng.uniform(0.28, 0.62) + rng.uniform(-0.18, 0.18))
        direction_x, direction_z = math.cos(angle), math.sin(angle)
        side_x, side_z = -direction_z, direction_x
        length = rng.uniform(0.18, 0.28) * (1.0 - 0.025 * leaf_index)
        max_width = rng.uniform(0.038, 0.058)
        stem_x, stem_y, stem_z = stem_center(attach_t)
        base = len(foliage_points)
        leaf_steps = 18
        for step in range(leaf_steps + 1):
            t = step / leaf_steps
            center_x = stem_x + direction_x * length * t
            center_z = stem_z + direction_z * length * t
            center_y = stem_y + length * (
                0.34 * math.sin(math.pi * t) - foliage_droop * t ** 1.45
            )
            envelope = math.sin(math.pi * t) ** 0.65
            lobes = 0.40 + 0.60 * (0.5 + 0.5 * math.cos(
                8.0 * math.pi * t + 0.7 * leaf_index
            ))
            width = max_width * envelope * lobes
            curl = 0.004 * math.sin(3.0 * math.pi * t + leaf_index)
            foliage_points += [
                (center_x - side_x * width, center_y + curl,
                 center_z - side_z * width),
                (center_x + side_x * width, center_y - curl,
                 center_z + side_z * width),
            ]
        for step in range(leaf_steps):
            a = base + 2 * step
            b, c, d = a + 1, a + 2, a + 3
            foliage_indices += [a, c, b, b, c, d, b, c, a, d, c, b]

    # Four broad petals in two overlapping pairs form a continuous asymmetric bowl.
    radial_steps, lateral_steps = 34, 96
    bloom_y = stem_top - 0.006
    phase = rng.uniform(0.0, 2.0 * math.pi)
    petal_angles = [phase, phase + math.pi, phase + 0.5 * math.pi,
                    phase + 1.5 * math.pi]
    for petal, nominal_angle in enumerate(petal_angles):
        angle = nominal_angle + rng.uniform(-0.09, 0.09)
        length = rng.uniform(0.108, 0.130)
        half_span = rng.uniform(1.20, 1.38)
        whorl_lift = 0.005 if petal >= 2 else 0.0
        side_tilt = rng.uniform(-0.014, 0.014)
        bowl_height = rng.uniform(0.088, 0.125)
        flop_center = rng.uniform(-0.62, 0.62)
        flop_width = rng.uniform(0.30, 0.58)
        flop_depth = rng.uniform(0.045, 0.080)
        edge_curl = rng.uniform(-0.025, 0.018)
        base = len(petal_points)
        for row in range(radial_steps + 1):
            u = row / radial_steps
            eased = u * u * (3.0 - 2.0 * u)
            angular_envelope = math.sin(0.5 * math.pi * (0.04 + 0.96 * u))
            for column in range(lateral_steps + 1):
                v = 2.0 * column / lateral_steps - 1.0
                theta = angle + v * (0.68 + (half_span - 0.50) * angular_envelope)
                rounded_side = 0.10 * eased * abs(v) ** 4
                low_rim_wave = 0.0030 * u ** 5 * math.sin(
                    3.0 * math.pi * v + 0.8 * petal
                )
                radius = 0.005 + length * (eased - rounded_side) + low_rim_wave
                bowl = 0.008 * u + bowl_height * u ** 1.80
                broad_crumple = 0.0065 * u ** 1.7 * math.sin(
                    5.0 * math.pi * v + 5.5 * u + phase + 0.6 * petal
                )
                fine_veins = u * (
                    0.0026 * math.sin(25.0 * math.pi * v + 2.3 * u + phase) +
                    0.00125 * math.sin(53.0 * math.pi * v - 4.1 * u + petal) +
                    0.00055 * math.sin(79.0 * math.pi * v + 7.0 * u + phase)
                )
                soft_edge = 0.0055 * u ** 6 * math.sin(
                    4.0 * math.pi * v + 1.3 * petal
                )
                localized_flop = -flop_depth * u ** 2.4 * math.exp(
                    -((v - flop_center) / flop_width) ** 2
                )
                margin_curl = edge_curl * u ** 3 * abs(v) ** 3
                y = (bloom_y + whorl_lift + bowl + broad_crumple + fine_veins + soft_edge +
                     localized_flop + margin_curl)
                y += side_tilt * v * u
                petal_points.append((lean_x + radius * math.cos(theta), y,
                                     lean_z + radius * math.sin(theta)))
        stride = lateral_steps + 1
        for row in range(radial_steps):
            for column in range(lateral_steps):
                a = base + row * stride + column
                b, c, d = a + 1, a + stride, a + stride + 1
                triangles = [a, c, b, b, c, d, b, c, a, d, c, b]
                column_center = 2.0 * (column + 0.5) / lateral_steps - 1.0
                if row < 7 and abs(column_center) < 0.42:
                    petal_base_indices += triangles
                elif row >= radial_steps - 4:
                    petal_rim_indices += triangles
                else:
                    petal_indices += triangles
        for row in range(radial_steps + 1):
            for column in range(lateral_steps + 1):
                before_u = base + max(0, row - 1) * stride + column
                after_u = base + min(radial_steps, row + 1) * stride + column
                before_v = base + row * stride + max(0, column - 1)
                after_v = base + row * stride + min(lateral_steps, column + 1)
                du = tuple(petal_points[after_u][i] - petal_points[before_u][i]
                           for i in range(3))
                dv = tuple(petal_points[after_v][i] - petal_points[before_v][i]
                           for i in range(3))
                normal = (dv[1] * du[2] - dv[2] * du[1],
                          dv[2] * du[0] - dv[0] * du[2],
                          dv[0] * du[1] - dv[1] * du[0])
                magnitude = math.sqrt(sum(value * value for value in normal))
                normal = ((0.0, 1.0, 0.0) if magnitude < 1e-10 else
                          tuple(value / magnitude for value in normal))
                if normal[1] < 0.0:
                    normal = tuple(-value for value in normal)
                petal_normals.append(normal)

    # A small dark receptacle closes the flower base beneath the organs.
    center_y = bloom_y + 0.018
    receptacle_segments = 24
    receptacle_points.append((lean_x, center_y - 0.003, lean_z))
    for segment in range(receptacle_segments):
        theta = 2.0 * math.pi * segment / receptacle_segments
        receptacle_points.append((lean_x + 0.017 * math.cos(theta), center_y,
                                  lean_z + 0.017 * math.sin(theta)))
    for segment in range(receptacle_segments):
        a = 1 + segment
        b = 1 + (segment + 1) % receptacle_segments
        receptacle_indices += [0, a, b, b, a, 0]

    # Dense stamens follow a golden-angle spiral through an irregular annulus.
    stamen_count = 2400
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    for stamen in range(stamen_count):
        theta = stamen * golden_angle + 0.19 * variant
        fraction = (stamen + 0.5) / stamen_count
        inner_radius = 0.0075 + 0.0243 * math.sqrt(fraction)
        inner_radius *= 1.0 + 0.045 * math.sin(7.0 * theta)
        outer_radius = inner_radius + 0.0025 + 0.0015 * math.sin(3.3 * theta) ** 2
        height = 0.018 + 0.016 * (0.30 + 0.70 * math.sin(4.7 * theta) ** 2)
        tangent_x, tangent_z = -math.sin(theta), math.cos(theta)
        radial_x, radial_z = math.cos(theta), math.sin(theta)
        filament_radius = 0.00062
        base = len(filament_points)
        filament_segments = 5
        filament_sides = 8
        for segment in range(filament_segments + 1):
            t = segment / filament_segments
            radius = inner_radius + (outer_radius - inner_radius) * t
            bend = 0.0008 * math.sin(math.pi * t + 2.3 * theta)
            cx = lean_x + radius * math.cos(theta) + bend * tangent_x
            cz = lean_z + radius * math.sin(theta) + bend * tangent_z
            cy = center_y + height * t
            for side in range(filament_sides):
                phi = 2.0 * math.pi * side / filament_sides
                horizontal = filament_radius * math.cos(phi)
                vertical = filament_radius * math.sin(phi)
                filament_points.append((
                    cx + horizontal * tangent_x,
                    cy + vertical,
                    cz + horizontal * tangent_z,
                ))
        for segment in range(filament_segments):
            for side in range(filament_sides):
                a = base + segment * filament_sides + side
                b = base + segment * filament_sides + (side + 1) % filament_sides
                c, d = a + filament_sides, b + filament_sides
                filament_indices += [a, c, b, b, c, d]

        # Each filament terminates in a vertically elongated anther whose long
        # axis continues the filament rather than lying across it.
        tip_x = lean_x + outer_radius * math.cos(theta)
        tip_z = lean_z + outer_radius * math.sin(theta)
        tip_y = center_y + height
        base = len(anther_points)
        anther_rings, anther_segments = 5, 8
        for ring in range(anther_rings + 1):
            latitude = math.pi * ring / anther_rings
            for segment in range(anther_segments):
                longitude = 2.0 * math.pi * segment / anther_segments
                radial_offset = 0.00082 * math.sin(latitude) * math.cos(longitude)
                tangent_offset = 0.00082 * math.sin(latitude) * math.sin(longitude)
                vertical = 0.00275 * math.cos(latitude)
                anther_points.append((
                    tip_x + radial_offset * radial_x + tangent_offset * tangent_x,
                    tip_y + vertical,
                    tip_z + radial_offset * radial_z + tangent_offset * tangent_z,
                ))
        for ring in range(anther_rings):
            for segment in range(anther_segments):
                a = base + ring * anther_segments + segment
                b = base + ring * anther_segments + (segment + 1) % anther_segments
                c, d = a + anther_segments, b + anther_segments
                anther_indices += [a, c, b, b, c, d]

    # The pistil is one continuous polar surface.  Its upper ovary transitions
    # directly into a lobed, papillate stigma rather than carrying an added decal.
    capsule_rings, capsule_segments = 28, 144
    capsule_center_y = center_y + 0.017
    stigma_boundary = 0.82
    stigma_faces = []
    ovary_faces = []
    for ring in range(capsule_rings + 1):
        polar = math.pi * ring / capsule_rings
        for segment in range(capsule_segments):
            theta = 2.0 * math.pi * segment / capsule_segments
            # The cylindrical stigma experiment requires a smooth ovary below
            # the tubes; retaining the former raised ridges causes intersections.
            rib = 1.0
            radial = 0.0122 * math.sin(polar) ** 0.84 * rib
            height = capsule_center_y + 0.0172 * math.cos(polar)
            capsule_points.append((lean_x + radial * math.cos(theta), height,
                                   lean_z + radial * math.sin(theta)))
    for ring in range(capsule_rings):
        polar_mid = math.pi * (ring + 0.5) / capsule_rings
        for segment in range(capsule_segments):
            theta_mid = 2.0 * math.pi * (segment + 0.5) / capsule_segments
            a = ring * capsule_segments + segment
            b = ring * capsule_segments + (segment + 1) % capsule_segments
            c, d = a + capsule_segments, b + capsule_segments
            face = [a, c, b, b, c, d]
            arm = max(0.0, math.cos(16.0 * theta_mid)) ** 3.2
            rounded_extent = 0.69 + 0.13 * math.sqrt(arm)
            if polar_mid < 0.155 or (polar_mid < rounded_extent and arm > 0.14):
                stigma_faces += face
            else:
                ovary_faces += face
    # The tube experiment replaces the colored surface regions while retaining
    # their subtle relief beneath the fused arms.
    capsule_indices = ovary_faces + stigma_faces
    stigma_indices = []

    # Recompute smooth normals from the actually displaced surface so the
    # stigmatic ridges retain their three-dimensional relief under diffuse light.
    accumulated = [[0.0, 0.0, 0.0] for _ in capsule_points]
    all_faces = ovary_faces + stigma_faces
    for offset in range(0, len(all_faces), 3):
        ia, ib, ic = all_faces[offset:offset + 3]
        a, b, c = capsule_points[ia], capsule_points[ib], capsule_points[ic]
        ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        face_normal = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        for index in (ia, ib, ic):
            accumulated[index][0] += face_normal[0]
            accumulated[index][1] += face_normal[1]
            accumulated[index][2] += face_normal[2]
    for normal in accumulated:
        magnitude = math.sqrt(sum(value * value for value in normal)) or 1.0
        capsule_normals.append(tuple(value / magnitude for value in normal))

    # Sixteen curved tubes follow the ovary surface.  Their tapered end rings
    # form rounded tips, while their first rings overlap densely at the pole.
    stigma_arm_count = 16
    stigma_path_segments = 22
    stigma_tube_sides = 10
    stigma_radius = 0.00082
    for arm_index in range(stigma_arm_count):
        theta = 2.0 * math.pi * arm_index / stigma_arm_count
        base = len(stigma_tube_points)
        for path_index in range(stigma_path_segments + 1):
            t = path_index / stigma_path_segments
            polar = -0.10 + 0.90 * t
            sine_polar = math.sin(polar)
            radial = 0.0122 * math.copysign(abs(sine_polar) ** 0.84,
                                            sine_polar)
            surface_y = capsule_center_y + 0.0172 * math.cos(polar)
            normal = (math.sin(polar) * math.cos(theta), math.cos(polar),
                      math.sin(polar) * math.sin(theta))
            azimuth = (-math.sin(theta), 0.0, math.cos(theta))
            end_rounding = min(1.0,
                               (stigma_path_segments - path_index) / 2.5)
            local_radius = stigma_radius * math.sqrt(max(0.0, end_rounding))
            center = (
                lean_x + radial * math.cos(theta) + normal[0] * stigma_radius * 0.32,
                surface_y + normal[1] * stigma_radius * 0.32,
                lean_z + radial * math.sin(theta) + normal[2] * stigma_radius * 0.32,
            )
            for side in range(stigma_tube_sides):
                phi = 2.0 * math.pi * side / stigma_tube_sides
                stigma_tube_points.append((
                    center[0] + local_radius * (math.cos(phi) * normal[0] +
                                                math.sin(phi) * azimuth[0]),
                    center[1] + local_radius * math.cos(phi) * normal[1],
                    center[2] + local_radius * (math.cos(phi) * normal[2] +
                                                math.sin(phi) * azimuth[2]),
                ))
        for path_index in range(stigma_path_segments):
            for side in range(stigma_tube_sides):
                a = base + path_index * stigma_tube_sides + side
                b = base + path_index * stigma_tube_sides + (side + 1) % stigma_tube_sides
                c, d = a + stigma_tube_sides, b + stigma_tube_sides
                stigma_tube_indices += [a, c, b, b, c, d]


    return {
        "stem": (stem_points, stem_indices),
        "foliage": (foliage_points, foliage_indices),
        "buds": (bud_points, bud_indices),
        "petals": (petal_points, petal_indices, petal_normals),
        "petal_bases": (petal_points, petal_base_indices, petal_normals),
        "petal_rims": (petal_points, petal_rim_indices, petal_normals),
        "receptacle": (receptacle_points, receptacle_indices),
        "filaments": (filament_points, filament_indices),
        "anthers": (anther_points, anther_indices),
        "capsule": (capsule_points, capsule_indices, capsule_normals),
        "stigma": (stigma_tube_points, stigma_tube_indices),
    }


def write_terrain_details(lines, terrain, config, camera=None, film=None):
    """Write reusable ground-detail objects and terrain-aware instances."""

    if terrain is None:
        return
    details = config.get("details", {})
    grass = details.get("grass", {})
    grass_layers = grass.get("layers", [])
    if grass_layers:
        grass_defaults = {key: value for key, value in grass.items() if key != "layers"}
        grasses = [
            (f"grass_{index}", {**grass_defaults, **layer}, _grass_mesh)
            for index, layer in enumerate(grass_layers)
        ]
    else:
        grasses = [("grass", grass, _grass_mesh)]
    layers = grasses + [
        ("poppies", details.get("poppies", {}), _poppy_mesh),
        ("litter", details.get("litter", {}), None),
        ("rocks", details.get("rocks", {}), None),
        ("undergrowth", details.get("undergrowth", {}), _fern_mesh),
    ]
    enabled_layers = [(name, cfg, mesh) for name, cfg, mesh in layers
                      if cfg.get("enabled", False)]
    if not enabled_layers:
        return
    lines += ['# Terrain detail object definitions']
    for layer_index, (name, layer, mesh_factory) in enumerate(enabled_layers):
        colors = layer.get("reflectance_variants", [[0.08, 0.22, 0.035]])
        variants = max(1, int(layer.get("variants", len(colors))))
        for variant in range(variants):
            color = colors[variant % len(colors)]
            lines.append(f'ObjectBegin "terrain_{name}_{variant}"')
            if name != "poppies":
                surface = layer.get("surface", {})
                surface_type = surface.get("type", "diffuse")
                if surface_type == "coateddiffuse":
                    roughness = float(surface.get("roughness", 0.15))
                    eta = float(surface.get("eta", 1.33))
                    thickness = float(surface.get("thickness", 0.002))
                    if roughness < 0.0 or eta <= 0.0 or thickness < 0.0:
                        raise ValueError(
                            "coated terrain-detail surface values must be nonnegative "
                            "and eta must be positive"
                        )
                    lines.append(
                        f'    Material "coateddiffuse" '
                        f'"rgb reflectance" [ {color[0]} {color[1]} {color[2]} ] '
                        f'"float roughness" [ {roughness} ] '
                        f'"float eta" [ {eta} ] '
                        f'"float thickness" [ {thickness} ]'
                    )
                elif surface_type == "diffuse":
                    lines.append(
                        f'    Material "diffuse" "rgb reflectance" [ {color[0]} {color[1]} {color[2]} ]'
                    )
                else:
                    raise ValueError(
                        f"unsupported terrain-detail surface type {surface_type!r}"
                    )
            if name == "rocks":
                lines.append('    Shape "sphere" "float radius" [ 1 ]')
            elif name == "litter":
                _write_detail_mesh(
                    lines,
                    [(-0.18, 0.0, -0.5), (0.0, 0.035, 0.0),
                     (0.18, 0.0, -0.5), (0.0, 0.015, 0.5)],
                    [0, 1, 3, 1, 2, 3, 3, 1, 0, 3, 2, 1],
                )
            else:
                if mesh_factory is _grass_mesh:
                    points, indices = mesh_factory(variant, layer)
                elif mesh_factory is _poppy_mesh:
                    parts = mesh_factory(variant, layer)
                    stem_color = layer.get("stem_reflectance", [0.035, 0.16, 0.025])
                    foliage_color = layer.get("foliage_reflectance", [0.09, 0.22, 0.07])
                    center_colors = layer.get("center_reflectance_variants", [
                        layer.get("center_reflectance", [0.012, 0.006, 0.004])
                    ])
                    capsule_colors = layer.get("capsule_reflectance_variants", [
                        layer.get("capsule_reflectance", [0.34, 0.42, 0.12])
                    ])
                    anther_color = layer.get("anther_reflectance", [0.055, 0.010, 0.025])
                    stigma_color = layer.get("stigma_reflectance", [0.52, 0.53, 0.18])
                    blotch_flags = layer.get("basal_blotch_variants", [True])
                    blotch_enabled = bool(blotch_flags[variant % len(blotch_flags)])
                    blotch_color = layer.get("basal_blotch_reflectance", [0.012, 0.003, 0.009])
                    center_color = center_colors[variant % len(center_colors)]
                    capsule_color = capsule_colors[variant % len(capsule_colors)]
                    lines.append(
                        f'    Material "diffuse" "rgb reflectance" [ {stem_color[0]} {stem_color[1]} {stem_color[2]} ]'
                    )
                    _write_detail_mesh(lines, *parts["stem"])
                    lines.append(
                        f'    Material "diffuse" "rgb reflectance" [ {foliage_color[0]} {foliage_color[1]} {foliage_color[2]} ]'
                    )
                    _write_detail_mesh(lines, *parts["foliage"])
                    _write_detail_mesh(lines, *parts["buds"])
                    transmission = layer.get("petal_transmittance", [0.30, 0.018, 0.002])
                    rim_transmission = layer.get("rim_transmittance", [0.42, 0.028, 0.003])
                    dark = [0.55 * value for value in color]
                    light = [min(1.0, 0.88 * value + 0.035) for value in color]
                    texture_prefix = f"poppy_{variant}"
                    lines += [
                        '    TransformBegin',
                        '        Scale 0.028 0.070 0.028',
                        f'        Texture "{texture_prefix}_fiber" "float" "fbm"',
                        '            "integer octaves" [ 6 ]',
                        '            "float roughness" [ 0.68 ]',
                        '    TransformEnd',
                        f'    Texture "{texture_prefix}_dark" "spectrum" "constant"',
                        f'        "rgb value" [ {dark[0]} {dark[1]} {dark[2]} ]',
                        f'    Texture "{texture_prefix}_light" "spectrum" "constant"',
                        f'        "rgb value" [ {light[0]} {light[1]} {light[2]} ]',
                        f'    Texture "{texture_prefix}_color" "spectrum" "mix"',
                        f'        "texture tex1" [ "{texture_prefix}_dark" ]',
                        f'        "texture tex2" [ "{texture_prefix}_light" ]',
                        f'        "texture amount" [ "{texture_prefix}_fiber" ]',
                        f'    Material "diffusetransmission" "texture reflectance" [ "{texture_prefix}_color" ] '
                        f'"rgb transmittance" [ {transmission[0]} {transmission[1]} {transmission[2]} ]',
                    ]
                    _write_detail_mesh(lines, *parts["petals"])
                    if blotch_enabled:
                        lines.append(
                            f'    Material "diffuse" "rgb reflectance" [ {blotch_color[0]} {blotch_color[1]} {blotch_color[2]} ]'
                        )
                    _write_detail_mesh(lines, *parts["petal_bases"])
                    lines.append(
                        f'    Material "diffusetransmission" "texture reflectance" [ "{texture_prefix}_color" ] '
                        f'"rgb transmittance" [ {rim_transmission[0]} {rim_transmission[1]} {rim_transmission[2]} ]'
                    )
                    _write_detail_mesh(lines, *parts["petal_rims"])
                    lines.append(
                        f'    Material "diffuse" "rgb reflectance" [ {center_color[0]} {center_color[1]} {center_color[2]} ]'
                    )
                    _write_detail_mesh(lines, *parts["receptacle"])
                    _write_detail_mesh(lines, *parts["filaments"])
                    lines.append(
                        f'    Material "diffuse" "rgb reflectance" [ {anther_color[0]} {anther_color[1]} {anther_color[2]} ]'
                    )
                    _write_detail_mesh(lines, *parts["anthers"])
                    lines.append(
                        f'    Material "diffuse" "rgb reflectance" [ {capsule_color[0]} {capsule_color[1]} {capsule_color[2]} ]'
                    )
                    _write_detail_mesh(lines, *parts["capsule"])
                    lines.append(
                        f'    Material "diffuse" "rgb reflectance" [ {stigma_color[0]} {stigma_color[1]} {stigma_color[2]} ]'
                    )
                    _write_detail_mesh(lines, *parts["stigma"])
                    points = indices = None
                else:
                    points, indices = mesh_factory()
                if points is not None:
                    _write_detail_mesh(lines, points, indices)
            lines += ['ObjectEnd', '']

        visibility_anchor = None
        placement_reference = layer.get("camera_frustum", {}).get(
            "placement_reference", "root"
        )
        if mesh_factory is _poppy_mesh and placement_reference == "flower":
            main_tropism = layer.get("tropism", {}).get("main_stem", {})
            stem_top = float(main_tropism.get("height", 0.765))
            stem_bend = float(main_tropism.get("bend", 0.145))
            stem_direction = math.radians(
                float(main_tropism.get("direction_degrees", 32.0))
            )
            # Count and frame-test the primary blossom, not its ground contact.
            # This permits roots below the lower edge when the blossom is visible.
            visibility_anchor = (
                stem_bend * math.cos(stem_direction),
                stem_top,
                stem_bend * math.sin(stem_direction),
            )
        points = scatter_points(
            terrain,
            layer,
            1000 * (layer_index + 1),
            camera=camera,
            film=film,
            visibility_anchor=visibility_anchor,
        )
        tropism = layer.get("blade", {}).get("tropism", {})
        tropism_enabled = bool(tropism.get("enabled", False))
        tropism_direction = float(tropism.get("direction_degrees", 0.0))
        tropism_field = tropism.get("field", {})
        field_seed = int(tropism_field.get("seed", layer.get("seed", 1)))
        random_jitter = float(tropism_field.get("random_jitter_degrees", 0.0))
        lines.append(f'# Terrain {name}: {len(points)} instances')
        for point in points:
            angle, axis = alignment_rotation(point.normal)
            sx = point.scale * point.aspect[0]
            sy = point.scale * point.aspect[1]
            sz = point.scale * point.aspect[2]
            instance_direction = point.rotation
            if tropism_enabled:
                field_offset = spatial_direction_offset(
                    point.position[0], point.position[2], tropism_field, field_seed
                )
                jitter = random_jitter * (point.rotation / 180.0 - 1.0)
                instance_direction = tropism_direction + field_offset + jitter
            lines += [
                'AttributeBegin',
                f'    Translate {point.position[0]:.7f} {point.position[1]:.7f} {point.position[2]:.7f}',
                f'    Rotate {angle:.7f} {axis[0]:.7f} {axis[1]:.7f} {axis[2]:.7f}',
                f'    Rotate {instance_direction:.7f} 0 1 0',
                f'    Scale {sx:.7f} {sy:.7f} {sz:.7f}',
                f'    ObjectInstance "terrain_{name}_{point.variant}"',
                'AttributeEnd',
            ]
        lines.append('')


def write_lsystem_trees(lines, trees, terrain=None):
    """Write configuration-driven deterministic L-system conifers."""

    for tree_index, tree in enumerate(trees):
        if not tree.get("enabled", True):
            continue
        preset = tree.get("preset", "christmas_tree")
        placement = tree.get("terrain_placement", {})
        instances = tree.get("instances", [])
        origin = (0.0, 0.0, 0.0) if instances else tuple(
            float(v) for v in tree.get("origin", [0, 0, 0])
        )
        if not instances and terrain is not None and placement.get("enabled", False):
            sample = terrain.sample(origin[0], origin[2])
            origin = (
                origin[0],
                sample.height + float(placement.get("height_offset", 0.0)),
                origin[2],
            )
        wood = tree.get("wood_reflectance", [0.20, 0.09, 0.025])
        green = tree.get("foliage_reflectance", [0.025, 0.16, 0.035])
        if preset == "christmas_tree":
            generated_segments = christmas_tree(tree)
        elif preset == "live_oak":
            generated_segments = live_oak(tree)
        elif preset == "fractal_tree":
            generated_segments = fractal_tree(tree)
        else:
            raise ValueError("unsupported L-system tree preset")
        debug_render = tree.get("debug_render", {})
        tree_scale = float(tree.get("scale", 1.0))
        if tree_scale <= 0.0:
            raise ValueError("L-system tree scale must be positive")
        curve_mode = debug_render.get("mode", "cylinders") == "curves"
        curve_width = tree_scale * float(debug_render.get("width", 0.25))
        curve_color = debug_render.get("reflectance", [0.82, 0.42, 0.06])
        object_name = f'lsystem_{preset}_{tree_index}'
        lines.append(f'# L-system {preset} {tree_index}')
        if instances:
            lines.append(f'ObjectBegin "{object_name}"')
        for segment in generated_segments:
            start = tuple(
                tree_scale * segment.start[i] + origin[i] for i in range(3)
            )
            end = tuple(
                tree_scale * segment.end[i] + origin[i] for i in range(3)
            )
            color = green if segment.kind in ("foliage", "leaf") else wood
            if segment.kind == "leaf":
                write_lsystem_leaf(
                    lines, start, end, tree_scale * segment.radius0, color
                )
            elif curve_mode:
                write_curve_segment(
                    lines, start, end, curve_width, curve_color
                )
            else:
                write_oriented_cylinder(
                    lines, start, end,
                    0.5 * tree_scale * (segment.radius0 + segment.radius1), color,
                )
        if instances:
            lines += ['ObjectEnd', '']
            for instance in instances:
                position = tuple(float(v) for v in instance["position"])
                if terrain is not None and placement.get("enabled", False):
                    sample = terrain.sample(position[0], position[2])
                    position = (
                        position[0],
                        sample.height + float(placement.get("height_offset", 0.0)),
                        position[2],
                    )
                instance_scale = float(instance.get("scale", 1.0))
                if instance_scale <= 0.0:
                    raise ValueError("L-system instance scale must be positive")
                lines += [
                    'AttributeBegin',
                    f'    Translate {position[0]:.9f} {position[1]:.9f} {position[2]:.9f}',
                    f'    Rotate {float(instance.get("rotation_y", 0.0)):.9f} 0 1 0',
                    f'    Scale {instance_scale:.9f} {instance_scale:.9f} {instance_scale:.9f}',
                    f'    ObjectInstance "{object_name}"',
                    'AttributeEnd',
                ]
        lines.append('')


def write_sunflower_support(lines, pattern_index, pattern, max_radius):
    """Write the underside, bracts, stem, and stem leaves for a flower head."""

    support = pattern.get("support", {})
    if not support.get("enabled", False):
        return

    center = tuple(float(value) for value in pattern.get("center", [0, 0, 0]))
    head_pitch = float(pattern.get("head_pitch", 0.0))
    pitch_radians = math.radians(head_pitch)

    def rotate_with_head(point):
        """Rotate a head-local point about the flower center around X."""

        dy = point[1] - center[1]
        dz = point[2] - center[2]
        return (
            point[0],
            center[1] + dy * math.cos(pitch_radians) - dz * math.sin(pitch_radians),
            center[2] + dy * math.sin(pitch_radians) + dz * math.cos(pitch_radians),
        )

    underside = support.get("underside", {})
    if underside.get("enabled", True):
        radius = float(underside.get("radius", max_radius * 1.02))
        height = float(underside.get("height", 4.0))
        offset_y = float(underside.get("offset_y", -3.5))
        color = underside.get("reflectance", [0.08, 0.20, 0.025])
        underside_center = rotate_with_head(
            (center[0], center[1] + offset_y, center[2])
        )
        lines += [
            '# sunflower receptacle underside',
            'AttributeBegin',
            (
                '    Material "diffuse"  "rgb reflectance" '
                f'[ {color[0]} {color[1]} {color[2]} ]'
            ),
            (
                f'    Translate {underside_center[0]:.9f} '
                f'{underside_center[1]:.9f} {underside_center[2]:.9f}'
            ),
            f'    Rotate {head_pitch:.9f} 1 0 0',
            f'    Scale {radius} {height} {radius}',
            '    Shape "sphere"  "float radius" [ 1 ]',
            'AttributeEnd',
            '',
        ]

    bracts = support.get("bracts", {})
    if bracts.get("enabled", True):
        bract_object = f"phyllotaxis_{pattern_index}_bract"
        write_phyllotaxis_organ(lines, bract_object, bracts)
        count = int(bracts.get("count", 34))
        ring_radius = float(bracts.get("ring_radius", max_radius * 0.92))
        offset_y = float(bracts.get("offset_y", -2.5))
        tilt = float(bracts.get("tilt", -18.0))
        for index in range(count):
            angle = index * 360.0 / count
            angle_rad = math.radians(angle)
            point = rotate_with_head((
                center[0] + ring_radius * math.cos(angle_rad),
                center[1] + offset_y,
                center[2] + ring_radius * math.sin(angle_rad),
            ))
            tangent_x = -math.sin(angle_rad)
            tangent_z = math.cos(angle_rad)
            lines += [
                'AttributeBegin',
                f'    Translate {point[0]:.9f} {point[1]:.9f} {point[2]:.9f}',
                f'    Rotate {head_pitch:.9f} 1 0 0',
                f'    Rotate {tilt:.9f} {tangent_x:.9f} 0 {tangent_z:.9f}',
                f'    Rotate {-angle:.9f} 0 1 0',
                f'    ObjectInstance "{bract_object}"',
                'AttributeEnd',
            ]
        lines.append('')

    stem = support.get("stem", {})
    if stem.get("enabled", True):
        top_y = center[1] + float(stem.get("top_offset_y", -3.0))
        top_z = center[2] + float(stem.get("top_offset_z", 0.0))
        length = float(stem.get("length", 68.0))
        segments = int(stem.get("segments", 18))
        base_radius = float(stem.get("base_radius", 2.3))
        tip_radius = float(stem.get("tip_radius", 1.35))
        sway = float(stem.get("sway", 1.2))
        color = stem.get("reflectance", [0.10, 0.28, 0.035])
        if segments < 1 or length <= 0 or base_radius <= 0 or tip_radius <= 0:
            raise ValueError("invalid sunflower stem dimensions")

        stem_points = []
        for index in range(segments + 1):
            t = index / segments
            y = top_y - length * (1.0 - t)
            envelope = math.sin(math.pi * t)
            x = center[0] + sway * envelope * math.sin(1.3 * math.pi * t)
            z = (
                center[2]
                + (top_z - center[2]) * t
                + 0.55 * sway * envelope * math.sin(1.7 * math.pi * t)
            )
            stem_points.append((x, y, z))

        for index in range(segments):
            t = index / segments
            radius = base_radius + (tip_radius - base_radius) * t
            write_oriented_cylinder(
                lines, stem_points[index], stem_points[index + 1], radius, color
            )
        rib_count = int(stem.get("rib_count", 0))
        rib_radius = float(stem.get("rib_radius", 0.045))
        rib_color = stem.get("rib_reflectance", [
            min(1.0, color[0] * 1.35),
            min(1.0, color[1] * 1.35),
            min(1.0, color[2] * 1.35),
        ])
        for rib in range(rib_count):
            angle = 2.0 * math.pi * rib / rib_count
            cosine = math.cos(angle)
            sine = math.sin(angle)
            for index in range(segments):
                t0 = index / segments
                t1 = (index + 1) / segments
                radius0 = base_radius + (tip_radius - base_radius) * t0
                radius1 = base_radius + (tip_radius - base_radius) * t1
                start = (
                    stem_points[index][0] + 0.98 * radius0 * cosine,
                    stem_points[index][1],
                    stem_points[index][2] + 0.98 * radius0 * sine,
                )
                end = (
                    stem_points[index + 1][0] + 0.98 * radius1 * cosine,
                    stem_points[index + 1][1],
                    stem_points[index + 1][2] + 0.98 * radius1 * sine,
                )
                write_oriented_cylinder(lines, start, end, rib_radius, rib_color)
        for index, point in enumerate(stem_points[1:-1], start=1):
            t = index / segments
            radius = base_radius + (tip_radius - base_radius) * t
            lines += [
                'AttributeBegin',
                (
                    '    Material "diffuse"  "rgb reflectance" '
                    f'[ {color[0]} {color[1]} {color[2]} ]'
                ),
                f'    Translate {point[0]:.9f} {point[1]:.9f} {point[2]:.9f}',
                f'    Shape "sphere"  "float radius" [ {radius:.9f} ]',
                'AttributeEnd',
            ]
        lines.append('')

        leaves = support.get("leaves", {})
        if leaves.get("enabled", True):
            leaf_object = f"phyllotaxis_{pattern_index}_stem_leaf"
            write_phyllotaxis_organ(lines, leaf_object, leaves)
            leaf_count = int(leaves.get("count", 9))
            divergence = float(leaves.get("divergence_angle", 137.5))
            lower_fraction = float(leaves.get("lower_fraction", 0.18))
            upper_fraction = float(leaves.get("upper_fraction", 0.82))
            inclination = float(leaves.get("inclination", 18.0))
            for index in range(leaf_count):
                fraction = (
                    lower_fraction
                    if leaf_count == 1
                    else lower_fraction
                    + (upper_fraction - lower_fraction) * index / (leaf_count - 1)
                )
                point_index = min(segments, max(0, round(fraction * segments)))
                point = stem_points[point_index]
                angle = index * divergence
                angle_rad = math.radians(angle)
                tangent_x = -math.sin(angle_rad)
                tangent_z = math.cos(angle_rad)
                lines += [
                    'AttributeBegin',
                    f'    Translate {point[0]:.9f} {point[1]:.9f} {point[2]:.9f}',
                    f'    Rotate {-inclination:.9f} {tangent_x:.9f} 0 {tangent_z:.9f}',
                    f'    Rotate {-angle:.9f} 0 1 0',
                    f'    ObjectInstance "{leaf_object}"',
                    'AttributeEnd',
                ]
            lines.append('')


def write_planar_phyllotaxis(lines, patterns):
    """Write Vogel-model patterns, including optional sunflower head zones."""

    for pattern_index, pattern in enumerate(patterns):
        if not pattern.get("enabled", True):
            continue

        count = pattern["count"]
        spacing = float(pattern.get("spacing", 1.0))
        center = pattern.get("center", [0.0, 0.0, 0.0])
        surface = pattern.get("surface", {"type": "plane"})
        surface_type = surface.get("type", "plane")
        head_pitch = float(pattern.get("head_pitch", 0.0))
        pitch_radians = math.radians(head_pitch)
        dome_height_value = 0.0
        if surface_type == "plane":
            height_function = None
        elif surface_type in ("dome", "area_dome"):
            dome_height_value = float(surface.get("height", 0.0))
            height_function = dome_height(dome_height_value)
        else:
            raise ValueError(
                f"Unsupported planar phyllotaxis surface: {surface_type}"
            )

        max_radius = float(surface.get(
            "radius", spacing * (max(1, count - 1) ** 0.5)
        ))
        if surface_type == "area_dome":
            points = area_dome_points(
                count=count,
                divergence_angle=float(pattern.get("divergence_angle", 137.5)),
                radius=max_radius,
                height=dome_height_value,
                center=center,
            )
        else:
            points = vogel_points(
                count=count,
                divergence_angle=float(pattern.get("divergence_angle", 137.5)),
                spacing=spacing,
                center=center,
                height_function=height_function,
            )

        def rotate_with_head(point):
            dy = point[1] - center[1]
            dz = point[2] - center[2]
            return (
                point[0],
                center[1] + dy * math.cos(pitch_radians) - dz * math.sin(pitch_radians),
                center[2] + dy * math.sin(pitch_radians) + dz * math.cos(pitch_radians),
            )

        write_sunflower_support(lines, pattern_index, pattern, max_radius)

        receptacle = pattern.get("receptacle", {})
        if receptacle.get("enabled", False):
            receptacle_radius = float(receptacle.get("radius", max_radius + spacing))
            receptacle_height = float(receptacle.get("height", dome_height_value))
            reflectance = receptacle.get("reflectance", [0.20, 0.12, 0.025])
            lines += [
                f'# {pattern.get("label", f"planar_phyllotaxis_{pattern_index}")}',
                'AttributeBegin',
                (
                    '    Material "diffuse"  "rgb reflectance" '
                    f'[ {reflectance[0]} {reflectance[1]} {reflectance[2]} ]'
                ),
                f'    Translate {center[0]} {center[1]} {center[2]}',
                f'    Rotate {head_pitch:.9f} 1 0 0',
                f'    Scale {receptacle_radius} {receptacle_height} {receptacle_radius}',
                '    Shape "sphere"  "float radius" [ 1 ]',
                'AttributeEnd',
                '',
            ]

        zones = pattern.get("zones")
        if zones is None:
            zones = [{"index_min": 0, "index_max": count - 1,
                      "organ": pattern.get("organ", {})}]

        object_names = []
        for zone_index, zone in enumerate(zones):
            object_name = f"phyllotaxis_{pattern_index}_organ_{zone_index}"
            object_names.append(object_name)
            write_phyllotaxis_organ(lines, object_name, zone.get("organ", {}))

        for point in points:
            matching_zone = None
            matching_zone_index = None
            for zone_index, zone in enumerate(zones):
                index_min = int(zone.get("index_min", 0))
                index_max = int(zone.get("index_max", count - 1))
                if index_min <= point.index <= index_max:
                    matching_zone = zone
                    matching_zone_index = zone_index
                    break
            if matching_zone is None:
                continue

            organ = matching_zone.get("organ", {})
            shape = organ.get("shape", "sphere")
            radial_angle = point.angle_degrees % 360.0
            radial_scale = float(organ.get("radial_scale", 1.0))
            radial_offset = float(organ.get("radial_offset", 0.0))
            effective_radius = max(0.0, point.radius * radial_scale + radial_offset)
            radial_fraction = min(1.0, effective_radius / max_radius)
            variation_phase = math.sin(
                (point.index + 1) * 12.9898 + matching_zone_index * 78.233
            )
            variation = variation_phase - math.floor(variation_phase)
            signed_variation = 2.0 * variation - 1.0
            tilt = 0.0
            if surface_type == "dome" and effective_radius < max_radius:
                denominator = max(1e-6, (1.0 - radial_fraction ** 2) ** 0.5)
                slope = -dome_height_value * effective_radius / (max_radius ** 2 * denominator)
                tilt = min(80.0, math.degrees(math.atan(-slope)))
            elif surface_type == "area_dome":
                slope = -2.0 * dome_height_value * effective_radius / (max_radius ** 2)
                tilt = min(80.0, math.degrees(math.atan(-slope)))
            organ_tilt = (
                float(organ.get("tilt", 0.0))
                + float(organ.get("tilt_by_radius", 0.0)) * radial_fraction
                + float(organ.get("tilt_jitter", 0.0)) * signed_variation
            )
            altitude = (
                float(organ.get("altitude", 0.0))
                + float(organ.get("altitude_by_radius", 0.0)) * radial_fraction
                + float(organ.get("altitude_jitter", 0.0)) * signed_variation
            )
            rotation_jitter = float(organ.get("rotation_jitter", 0.0))
            local_rotation = rotation_jitter * signed_variation
            scale_jitter = float(organ.get("scale_jitter", 0.0))
            organ_scale = max(0.05, 1.0 + scale_jitter * signed_variation)
            organ_scale *= max(
                0.05,
                1.0 + float(organ.get("scale_by_radius", 0.0)) * radial_fraction,
            )
            tangent_x = -math.sin(math.radians(radial_angle))
            tangent_z = math.cos(math.radians(radial_angle))
            radial_angle_radians = math.radians(radial_angle)
            local_y = point.y
            if surface_type == "area_dome":
                local_y = center[1] + dome_height_value * (
                    1.0 - radial_fraction * radial_fraction
                )
            elif surface_type == "dome":
                local_y = center[1] + dome_height_value * math.sqrt(
                    max(0.0, 1.0 - radial_fraction * radial_fraction)
                )
            rotated_point = rotate_with_head((
                center[0] + effective_radius * math.cos(radial_angle_radians),
                local_y + altitude,
                center[2] + effective_radius * math.sin(radial_angle_radians),
            ))

            lines += [
                'AttributeBegin',
                (
                    f'    Translate {rotated_point[0]:.9f} '
                    f'{rotated_point[1]:.9f} {rotated_point[2]:.9f}'
                ),
                f'    Rotate {head_pitch:.9f} 1 0 0',
            ]
            if organ_tilt != 0.0:
                lines.append(
                    f'    Rotate {organ_tilt:.9f} '
                    f'{tangent_x:.9f} 0 {tangent_z:.9f}'
                )
            if local_rotation != 0.0:
                lines.append(f'    Rotate {local_rotation:.9f} 0 1 0')
            if shape == "petal":
                lines += [
                    f'    Rotate {tilt:.9f} {tangent_x:.9f} 0 {tangent_z:.9f}',
                    f'    Rotate {-radial_angle:.9f} 0 1 0',
                ]
            elif tilt != 0.0:
                lines.append(
                    f'    Rotate {tilt:.9f} {tangent_x:.9f} 0 {tangent_z:.9f}'
                )
            if organ_scale != 1.0:
                lines.append(
                    f'    Scale {organ_scale:.9f} {organ_scale:.9f} {organ_scale:.9f}'
                )
            lines += [
                f'    ObjectInstance "{object_names[matching_zone_index]}"',
                'AttributeEnd',
            ]
        lines.append("")


# ==============================================================
# SECTION 6 — WRITE SCENE FILE (scene_files/scene.pbrt)
# ==============================================================

def write_scene(cfg, scene_root, medium_rel_path):
    """
    Assemble and write scene_files/scene.pbrt from config.json.

    Calls each section writer in the correct pbrt-v4 order:
      Pre-world:  header, camera, sampler, integrator, film, medium Include
      World:      WorldBegin, lights, geometry

    Config reads: all of scene.*
    Output file:  scene.master_file (relative to working-scene root)
    """
    scene    = cfg["scene"]
    out_path = os.path.join(scene_root, scene["master_file"])
    lines    = []

    # --- Pre-world section ---
    write_header(lines, scene.get("name", "untitled_scene"))
    write_fog_medium(cfg, lines)
    write_camera(lines, scene["camera"])
    write_sampler(lines, scene["sampler"])
    write_integrator(lines, scene["integrator"])
    lines.append("")
    write_film(lines, scene["film"], scene["output_filename"])
    

    # --- World section ---
    lines += ["WorldBegin", ""]
    write_fog_boundary(lines, scene.get("fog"))
    sky_config = scene.get("sky", {})
    cloud_formations = write_cloud_media(
        lines, sky_config.get("clouds", {}), scene_root
    )
    rain_curtains = write_rain_media(lines, scene.get("rain", {}))
    
    if medium_rel_path is not None:
        write_medium_include(lines, medium_rel_path)
    landscape_config = scene.get("landscape", {})
    ground_config = landscape_config.get("ground", {})
    terrain = create_terrain(ground_config)
    lights = []
    background = sky_config.get("background")
    if background:
        lights.append(background)
    lights.extend(scene.get("lights", []))
    write_lights(lines, lights)
    fog_enabled = bool(scene.get("fog", {}).get("enabled", False))
    write_cloud_boundaries(
        lines,
        cloud_formations,
        exterior_medium="fog" if fog_enabled else "",
    )
    write_rain_boundaries(
        lines,
        rain_curtains,
        exterior_medium="fog" if fog_enabled else "",
    )
    write_sun_aperture(lines, scene.get("sun_aperture"), lights)
    write_geometry(lines, scene.get("geometry", []), scene_root)
    write_terrain(lines, terrain, ground_config, scene_root)
    write_terrain_details(
        lines,
        terrain,
        ground_config,
        camera=scene.get("camera"),
        film=scene.get("film"),
    )
    write_distant_hills(
        lines,
        landscape_config.get("distant_hills", {}),
        ground_config.get("details", {}).get("grass", {}),
        ground_config.get("details", {}).get("poppies", {}),
    )
    write_planar_phyllotaxis(lines, scene.get("planar_phyllotaxis", []))
    write_lsystem_trees(lines, scene.get("lsystem_trees", []), terrain)

    grove_cfg = scene.get("grove", {})
    grove_tree_index = grove_cfg.get("tree_index", 0)

    # Define each generated tree once, then place either one ordinary
    # instance or the configured grove instances.
    for i, tree_cfg in enumerate(cfg["scene"].get("trees", [])):
        if not tree_cfg.get("enabled", False):
            continue
        lines += [
            f'ObjectBegin "tree_{i}_wood"',
            f'Include "scene_files/tree_{i}.pbrt"',
            'ObjectEnd',
            ''
        ]
        foliage_cfg = tree_cfg.get("foliage", {})
        if foliage_cfg.get("enabled", False):
            lines.append(f'Include "scene_files/foliage_defs_{i}.pbrt"')

        instances = [{}]
        if grove_cfg.get("enabled", False) and i == grove_tree_index:
            instances = grove_cfg.get("instances", [])

        for instance in instances:
            position = instance.get("position", [0.0, 0.0, 0.0])
            rotation = instance.get("rotation_y", 0.0)
            scale = instance.get("scale", 1.0)
            lines += [
                'AttributeBegin',
                f'    Translate {position[0]} {position[1]} {position[2]}',
                f'    Rotate {rotation} 0 1 0',
                f'    Scale {scale} {scale} {scale}',
                f'    ObjectInstance "tree_{i}_wood"'
            ]
            if foliage_cfg.get("enabled", False):
                lines.append(f'    Include "scene_files/foliage_{i}.pbrt"')
            lines += ['AttributeEnd', '']

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Written: {out_path}")


# ==============================================================
# SECTION 7 — ENTRY POINT
# ==============================================================

def main():
    """
    Entry point. Resolves config path, loads JSON, runs the build.

    Accepts an optional command-line argument for the config path.
    When called by render_pipeline.sh, the config path is passed
    explicitly. When run directly, defaults to config.json in the
    same directory as this script.
    """
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        script_dir  = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "config.json")

    if not os.path.isfile(config_path):
        print(f"ERROR: Config not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        cfg = json.load(f)

    scene_root = os.path.dirname(os.path.abspath(config_path))

    print(f"Building scene: {cfg['scene'].get('name', 'untitled_scene')}")
    medium_rel = write_medium(cfg, scene_root)
    write_scene(cfg, scene_root, medium_rel)
    print("Build complete.")


if __name__ == "__main__":
    main()
