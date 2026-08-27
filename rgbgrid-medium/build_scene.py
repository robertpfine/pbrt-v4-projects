#!/usr/bin/env python3
"""
build_scene.py  —  rgbgrid-medium project
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
from noise import pnoise2, pnoise3

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, REPOSITORY_ROOT)

from phyllotaxis import area_dome_points, dome_height, vogel_points
from fractal_tree import fractal_tree
from lsystem import christmas_tree, live_oak
from pasture_texture import generate_pasture_maps
from terrain import create_terrain
from terrain_details import alignment_rotation, scatter_points


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
        if nx < 2 or ny < 2 or nz < 2:
            raise ValueError("fog noise resolution values must be at least 2")
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
                    density.append(max(0.0, base_density + contrast * value))
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


def write_medium(cfg, project_root):
    """
    Generate scene_files/volumes/rgbgrid.pbrt.

    This file contains a single MakeNamedMedium block named "rgb_vol".
    It must be Included in the scene file BEFORE WorldBegin — pbrt
    requires named media to be declared in the pre-world section.

    Config reads:
      scene.grid            — grid dimensions, bounds, sigma_a
      scene.zones           — spectral zone definitions
      scene.generated_medium — output path (relative to project root)

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
    out    = os.path.join(project_root, scene["generated_medium"])

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

def write_header(lines, proj):
    """
    Write the comment header at the top of scene.pbrt.
    Config reads: project.name
    """
    lines += [
        "# FILE: scene.pbrt",
        f"# PROJECT: {proj['name']}",
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

    Input: medium_rel_path — path relative to the project root,
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
        threshold = float(aperture.get("open_threshold", 0.15))
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
                cloud_value = pnoise2(
                    local_u * frequency,
                    local_v * frequency,
                    octaves=octaves,
                    persistence=0.55,
                    lacunarity=2.0,
                    repeatx=4096,
                    repeaty=4096,
                    base=seed,
                )
                if cloud_value > threshold:
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


def write_geometry(lines, geometry):
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
        if mat["type"] == "diffuse":
            r = mat["reflectance"]
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


def write_terrain(lines, terrain, config, project_root):
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
    if surface.get("enabled", False) and surface.get("mode") == "pasture_texture":
        pasture = surface.get("pasture_texture", {})
        texture_directory = os.path.join(project_root, "scene_files", "textures")
        albedo_path, bump_path = generate_pasture_maps(pasture, texture_directory)
        albedo_relative = os.path.relpath(albedo_path, project_root)
        bump_relative = os.path.relpath(bump_path, project_root)
        bump_scale = float(pasture.get("bump_scale", 0.012))
        lines += [
            '    Texture "terrain_pasture_albedo" "spectrum" "imagemap"',
            f'        "string filename" [ "{albedo_relative}" ]',
            '        "string encoding" [ "sRGB" ]',
            '        "string wrap" [ "repeat" ]',
            '        "string filter" [ "ewa" ]',
        ]
        if bump_scale > 0.0:
            lines += [
                '    Texture "terrain_pasture_bump_raw" "float" "imagemap"',
                f'        "string filename" [ "{bump_relative}" ]',
                '        "string encoding" [ "linear" ]',
                '        "string wrap" [ "repeat" ]',
                '        "string filter" [ "ewa" ]',
                '    Texture "terrain_pasture_bump" "float" "scale"',
                '        "texture tex" [ "terrain_pasture_bump_raw" ]',
                f'        "float scale" [ {bump_scale} ]',
                '    Material "diffuse"',
                '        "texture reflectance" [ "terrain_pasture_albedo" ]',
                '        "texture displacement" [ "terrain_pasture_bump" ]',
            ]
        else:
            lines += [
                '    Material "diffuse"',
                '        "texture reflectance" [ "terrain_pasture_albedo" ]',
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
                '    Texture "terrain_pasture_color" "spectrum" "mix"',
                '        "texture tex1" [ "terrain_color" ]',
                '        "texture tex2" [ "terrain_fiber" ]',
                '        "texture amount" [ "terrain_fiber_amount" ]',
            ]
            terrain_color = "terrain_pasture_color"
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


def _write_detail_mesh(lines, points, indices):
    point_values = " ".join(f"{x:.6f} {y:.6f} {z:.6f}" for x, y, z in points)
    index_values = " ".join(str(value) for value in indices)
    lines += [
        '    Shape "trianglemesh"',
        f'        "integer indices" [ {index_values} ]',
        f'        "point3 P" [ {point_values} ]',
    ]


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


def write_terrain_details(lines, terrain, config):
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
            lines += [
                f'ObjectBegin "terrain_{name}_{variant}"',
                f'    Material "diffuse" "rgb reflectance" [ {color[0]} {color[1]} {color[2]} ]',
            ]
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
                else:
                    points, indices = mesh_factory()
                _write_detail_mesh(lines, points, indices)
            lines += ['ObjectEnd', '']

        points = scatter_points(terrain, layer, 1000 * (layer_index + 1))
        tropism = layer.get("blade", {}).get("tropism", {})
        tropism_enabled = bool(tropism.get("enabled", False))
        tropism_direction = float(tropism.get("direction_degrees", 0.0))
        lines.append(f'# Terrain {name}: {len(points)} instances')
        for point in points:
            angle, axis = alignment_rotation(point.normal)
            sx = point.scale * point.aspect[0]
            sy = point.scale * point.aspect[1]
            sz = point.scale * point.aspect[2]
            lines += [
                'AttributeBegin',
                f'    Translate {point.position[0]:.7f} {point.position[1]:.7f} {point.position[2]:.7f}',
                f'    Rotate {angle:.7f} {axis[0]:.7f} {axis[1]:.7f} {axis[2]:.7f}',
                f'    Rotate {(tropism_direction if tropism_enabled else point.rotation):.7f} 0 1 0',
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
        origin = tuple(float(v) for v in tree.get("origin", [0, 0, 0]))
        placement = tree.get("terrain_placement", {})
        if terrain is not None and placement.get("enabled", False):
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
        curve_mode = debug_render.get("mode", "cylinders") == "curves"
        curve_width = float(debug_render.get("width", 0.25))
        curve_color = debug_render.get("reflectance", [0.82, 0.42, 0.06])
        lines.append(f'# L-system {preset} {tree_index}')
        for segment in generated_segments:
            start = tuple(segment.start[i] + origin[i] for i in range(3))
            end = tuple(segment.end[i] + origin[i] for i in range(3))
            color = green if segment.kind in ("foliage", "leaf") else wood
            if segment.kind == "leaf":
                write_lsystem_leaf(
                    lines, start, end, segment.radius0, color
                )
            elif curve_mode:
                write_curve_segment(
                    lines, start, end, curve_width, curve_color
                )
            else:
                write_oriented_cylinder(
                    lines, start, end,
                    0.5 * (segment.radius0 + segment.radius1), color,
                )
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

def write_scene(cfg, project_root, medium_rel_path):
    """
    Assemble and write scene_files/scene.pbrt from config.json.

    Calls each section writer in the correct pbrt-v4 order:
      Pre-world:  header, camera, sampler, integrator, film, medium Include
      World:      WorldBegin, lights, geometry

    Config reads: all of scene.*, project.name
    Output file:  scene.master_file (relative to project root)
    """
    scene    = cfg["scene"]
    proj     = cfg["project"]
    out_path = os.path.join(project_root, scene["master_file"])
    lines    = []

    # --- Pre-world section ---
    write_header(lines, proj)
    write_fog_medium(cfg, lines)
    write_camera(lines, scene["camera"])
    write_sampler(lines, scene["sampler"])
    write_integrator(lines, scene["integrator"])
    lines.append("")
    write_film(lines, scene["film"], scene["output_filename"])
    

    # --- World section ---
    lines += ["WorldBegin", ""]
    write_fog_boundary(lines, scene.get("fog"))
    
    if medium_rel_path is not None:
        write_medium_include(lines, medium_rel_path)
    terrain_config = scene.get("terrain", {})
    terrain = create_terrain(terrain_config)
    lights = scene.get("lights", [])
    write_lights(lines, lights)
    write_sun_aperture(lines, scene.get("sun_aperture"), lights)
    write_geometry(lines, scene.get("geometry", []))
    write_terrain(lines, terrain, terrain_config, project_root)
    write_terrain_details(lines, terrain, terrain_config)
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

    project_root = os.path.dirname(os.path.abspath(config_path))

    print(f"Building project: {cfg['project']['name']}")
    medium_rel = write_medium(cfg, project_root)
    write_scene(cfg, project_root, medium_rel)
    print("Build complete.")


if __name__ == "__main__":
    main()
