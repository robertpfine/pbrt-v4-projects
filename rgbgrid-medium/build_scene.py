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
from noise import pnoise3


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
                if noise_enabled:
                    freq = noise_cfg.get("frequency", 0.5)
                    amp  = noise_cfg.get("amplitude", 0.15)
                    n = pnoise3(i * freq / nx, j * freq / ny, k * freq / nz)
                else:
                    n = 0.0

                # Accumulate RGB scattering from all enabled zones
                sr = sg = sb = 0.0
                for zone in zones:
                    if not zone.get("enabled", True):
                        continue

                    # Tent-function weight with optional noise position shift
                    t_shifted = t + n * amp if noise_enabled else t
                    d = abs(t_shifted - zone["position"])
                    w = max(0.0, 1.0 - d / zone["width"])

                    rgb = wavelength_to_rgb(zone["wavelength"])
                    sr += w * zone["strength"] * rgb[0]
                    sg += w * zone["strength"] * rgb[1]
                    sb += w * zone["strength"] * rgb[2]

                sigma_s      += [sr, sg, sb]
                sigma_a_flat += [sigma_a_val, sigma_a_val, sigma_a_val]

    return sigma_s, sigma_a_flat


# ==============================================================
# SECTION 4 — WRITE MEDIUM FILE (scene_files/volumes/rgbgrid.pbrt)
# ==============================================================

def write_fog_medium(cfg, lines):
    """
    Write a homogeneous fog medium named "fog" into the world section.
    This creates the exterior atmospheric medium that makes god rays visible.
    Config reads: scene.fog (enabled, sigma_a, sigma_s, g)

    pbrt note: MakeNamedMedium for homogeneous media can appear inside
    the world section, unlike rgbgrid which uses Include.
    """
    fog = cfg["scene"].get("fog")
    if not fog or not fog.get("enabled", True):
        return

    lines += [
        'MakeNamedMedium "fog"',
        '    "string type"  [ "homogeneous" ]',
        f'    "rgb sigma_a" [ {fog["sigma_a"]} {fog["sigma_a"]} {fog["sigma_a"]} ]',
        f'    "rgb sigma_s" [ {fog["sigma_s"]} {fog["sigma_s"]} {fog["sigma_s"]} ]',
        f'    "float g"     [ {fog["g"]} ]',
        '',
        'MediumInterface "" "fog"',
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
    zones  = scene["zones"]
    out    = os.path.join(project_root, scene["generated_medium"])

    print(f"  Building {g_cfg['nx']}x{g_cfg['ny']}x{g_cfg['nz']} rgbgrid "
          f"(axis={g_cfg['axis']}, sigma_a={g_cfg['sigma_a']})...")

    sigma_s, sigma_a_flat = compute_rgbgrid(g_cfg, zones)

    content = (
        f'MakeNamedMedium "rgb_vol"\n'
        f'    "string type"   [ "rgbgrid" ]\n'
        f'    "integer nx"    [ {g_cfg["nx"]} ]\n'
        f'    "integer ny"    [ {g_cfg["ny"]} ]\n'
        f'    "integer nz"    [ {g_cfg["nz"]} ]\n'
        # p0/p1 define the world-space bounding box of the volume
        f'    "point3 p0"     [ {g_cfg["world_min"][0]} {g_cfg["world_min"][1]} {g_cfg["world_min"][2]} ]\n'
        f'    "point3 p1"     [ {g_cfg["world_max"][0]} {g_cfg["world_max"][1]} {g_cfg["world_max"][2]} ]\n'
        # g is the Henyey-Greenstein anisotropy parameter: 0.0 = isotropic
        f'    "float g"       [ 0.0 ]\n'
        f'    "rgb sigma_a"   [\n'
        f'{fmt_floats(sigma_a_flat)}\n'
        f'    ]\n'
        f'    "rgb sigma_s"   [\n'
        f'{fmt_floats(sigma_s)}\n'
        f'    ]\n'
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
    Config reads: scene.lights[] (enabled, type, color_mode, temperature, scale, position)

    Supported light types:
      "infinite" — environment/sky light, no position
      "point"    — point light at a world-space position

    Supported color modes:
      "blackbody" — color temperature in Kelvin (physically based)
    """
    for light in lights:
        if not light.get("enabled", True):
            continue

        ltype = light["type"]
        mode  = light["color_mode"]
        temp  = light["temperature"]
        scale = light["scale"]

        if ltype == "infinite":
            lines.append(
                f'LightSource "infinite"'
                f'  "{mode} L" [ {temp} ]'
                f'  "float scale" [ {scale} ]'
            )

        elif ltype == "point":
            p = light["position"]
            lines.append(
                f'LightSource "point"'
                f'  "point3 from" [ {p[0]} {p[1]} {p[2]} ]'
                f'  "{mode} I" [ {temp} ]'
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
                f'  "{mode} I" [ {temp} ]'
                f'  "float scale" [ {scale} ]'
            )
    
        elif ltype == "distant":
            f = light["from"]
            t = light["to"]
            lines.append(
                f'LightSource "distant"'
                f'  "point3 from" [ {f[0]} {f[1]} {f[2]} ]'
                f'  "point3 to"   [ {t[0]} {t[1]} {t[2]} ]'
                f'  "{light["color_mode"]} L" [ {light["temperature"]} ]'
                f'  "float scale" [ {light["scale"]} ]'
            )
    
    lines.append("")


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
    
    write_medium_include(lines, medium_rel_path)
    write_lights(lines, scene.get("lights", []))
    write_geometry(lines, scene.get("geometry", []))

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