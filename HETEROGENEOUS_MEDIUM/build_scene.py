#!/usr/bin/env python3
import os
import json

# ---------------------------------------------------------------------------
# WAVELENGTH TO RGB
# ---------------------------------------------------------------------------
def wavelength_to_rgb(wl):
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

    if   380 <= wl < 420:
        factor = 0.3 + 0.7 * (wl - 380) / (420 - 380)
    elif 645 < wl <= 700:
        factor = 0.3 + 0.7 * (700 - wl) / (700 - 645)
    else:
        factor = 1.0

    return (r * factor, g * factor, b * factor)

# ---------------------------------------------------------------------------
# GRID BUILDER
# ---------------------------------------------------------------------------
def build_rgbgrid(grid_cfg, zones):
    nx, ny, nz = grid_cfg["nx"], grid_cfg["ny"], grid_cfg["nz"]
    axis = grid_cfg["axis"]
    sigma_a_val = grid_cfg["sigma_a"]

    sigma_s = []
    sigma_a_flat = []

    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                if   axis == "X": t = (i + 0.5) / nx
                elif axis == "Y": t = (j + 0.5) / ny
                else:             t = (k + 0.5) / nz

                sr, sg, sb = 0.0, 0.0, 0.0
                for zone in zones:
                    d = abs(t - zone["position"])
                    w = max(0.0, 1.0 - d / zone["width"])
                    rgb = wavelength_to_rgb(zone["wavelength"])
                    sr += w * zone["strength"] * rgb[0]
                    sg += w * zone["strength"] * rgb[1]
                    sb += w * zone["strength"] * rgb[2]

                sigma_s     += [sr, sg, sb]
                sigma_a_flat += [sigma_a_val, sigma_a_val, sigma_a_val]

    return sigma_s, sigma_a_flat

def fmt(values, per_line=9):
    lines = []
    for i in range(0, len(values), per_line):
        chunk = values[i:i + per_line]
        lines.append("        " + " ".join(f"{v:.5f}" for v in chunk))
    return "\n".join(lines)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "project_config.json")
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Resolve generation target paths
    generated_medium_rel = config["scene"]["generated_medium"]
    output_path = os.path.join(script_dir, generated_medium_rel)

    # Extract dynamic parameters from JSON config
    grid_cfg = config["scene"]["grid"]
    zones = config["scene"]["zones"]

    print(f"Building {grid_cfg['nx']}x{grid_cfg['ny']}x{grid_cfg['nz']} rgbgrid from config settings.")
    sigma_s, sigma_a_flat = build_rgbgrid(grid_cfg, zones)

    block = f"""MakeNamedMedium "rgb_vol"
    "string type"   [ "rgbgrid" ]
    "integer nx"    [ {grid_cfg['nx']} ]
    "integer ny"    [ {grid_cfg['ny']} ]
    "integer nz"    [ {grid_cfg['nz']} ]
    "point3 p0"      [ {grid_cfg['world_min']} {grid_cfg['world_min']} {grid_cfg['world_min']} ]
    "point3 p1"      [ {grid_cfg['world_max']} {grid_cfg['world_max']} {grid_cfg['world_max']} ]
    "float g"       [ 0.0 ]
    "rgb sigma_a"   [
{fmt(sigma_a_flat)}
    ]
    "rgb sigma_s"   [
{fmt(sigma_s)}
    ]
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(block)
    print(f"Written: {output_path}")

if __name__ == "__main__":
    main()