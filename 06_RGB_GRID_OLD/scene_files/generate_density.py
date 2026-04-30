"""
generate_density.py

Generates a pbrt-v4 "rgbgrid" medium density field consisting of
discrete spherical particle blobs, each assigned to the nearest
RGB emitter. Writes a complete .pbrt scene file ready to render.

Requirements:
    pip install numpy

Usage:
    python generate_density.py                        # writes pointillist_v4.pbrt
    python generate_density.py --out my_scene.pbrt    # custom output filename
    python generate_density.py --help                 # show all options

Render:
    pbrt --gpu pointillist_v4.pbrt
"""

import numpy as np
import argparse
import sys
from pathlib import Path


# =============================================================================
# Configuration — edit these or pass as command-line arguments
# =============================================================================

DEFAULTS = {
    # Grid resolution — increase for finer particle detail
    # Memory cost: nx * ny * nz * 3 * 4 bytes (three float channels)
    "nx": 64,
    "ny": 64,
    "nz": 64,

    # Number of particles
    "num_particles": 300,

    # Particle radius in voxels — primary "enlarged particle" control
    # 2.0 = small dots,  4.0 = medium,  8.0 = large dramatic blobs
    "particle_radius": 3.5,

    # Peak density value per blob (0..1 before scale is applied)
    "particle_peak": 0.8,

    # Medium scale — multiplies the entire density field
    # Raise if volume looks too transparent
    "medium_scale": 4.0,

    # Scattering asymmetry: 0=isotropic, 0.8=strong forward scattering
    "g": 0.0,

    # Emitter brightness (rgb L value)
    "emitter_intensity": 12.0,

    # Emitter sphere radius (world space)
    "emitter_radius": 0.12,

    # Enclosing sphere radius (world space)
    "enclosing_radius": 3.0,

    # Camera Z position (negative = in front of scene)
    "camera_z": -8.0,

    # Output filename
    "out": "pointillist_v4.pbrt",

    # Random seed for reproducibility
    "seed": 42,
}


# =============================================================================
# Emitter positions (world space) — triangle arrangement in XY plane
# Index: 0=red, 1=green, 2=blue
# =============================================================================
EMITTER_POSITIONS = np.array([
    [-1.0,  0.6,  0.0],   # red   — left
    [ 1.0,  0.6,  0.0],   # green — right
    [ 0.0, -0.8,  0.0],   # blue  — bottom
], dtype=np.float32)

EMITTER_COLORS = [
    (1.0, 0.0, 0.0),  # red
    (0.0, 1.0, 0.0),  # green
    (0.0, 0.0, 1.0),  # blue
]

EMITTER_NAMES = ["Red", "Green", "Blue"]


# =============================================================================
# Core functions
# =============================================================================

def world_to_grid_norm(world_pos: np.ndarray, enclosing_radius: float) -> np.ndarray:
    """Convert world-space position to normalised [0,1]^3 grid space."""
    return (world_pos + enclosing_radius) / (2.0 * enclosing_radius)


def paint_blob(grid: np.ndarray,
               center_vox: np.ndarray,
               radius_voxels: float,
               peak: float) -> None:
    """
    Paint a smooth spherical blob into a 3D density grid (in-place).
    Falloff: density = peak * (1 - (r/radius)^2)^2   for r < radius
    Grid shape: (nz, ny, nx)
    """
    nz, ny, nx = grid.shape
    r = radius_voxels

    x0 = max(0,    int(np.floor(center_vox[0] - r)))
    x1 = min(nx-1, int(np.ceil (center_vox[0] + r)))
    y0 = max(0,    int(np.floor(center_vox[1] - r)))
    y1 = min(ny-1, int(np.ceil (center_vox[1] + r)))
    z0 = max(0,    int(np.floor(center_vox[2] - r)))
    z1 = min(nz-1, int(np.ceil (center_vox[2] + r)))

    # Build coordinate arrays for the bounding box
    xs = np.arange(x0, x1+1, dtype=np.float32)
    ys = np.arange(y0, y1+1, dtype=np.float32)
    zs = np.arange(z0, z1+1, dtype=np.float32)

    # Squared distances from centre
    dx = (xs - center_vox[0])**2
    dy = (ys - center_vox[1])**2
    dz = (zs - center_vox[2])**2

    # Broadcast to 3D: shape (len_z, len_y, len_x)
    d2 = dz[:, None, None] + dy[None, :, None] + dx[None, None, :]
    r2 = r * r

    mask = d2 < r2
    t    = np.where(mask, 1.0 - d2 / r2, 0.0)
    vals = peak * t * t   # smooth falloff

    # Accumulate, clamp to 1.0
    region = grid[z0:z1+1, y0:y1+1, x0:x1+1]
    np.add(region, vals, out=region)
    np.clip(region, 0.0, 1.0, out=region)


def generate_particles(num_particles: int,
                       enclosing_radius: float,
                       emitter_positions_norm: np.ndarray,
                       seed: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate particle positions (normalised [0,1]^3) inside a sphere
    of radius 0.85 centred at (0.5, 0.5, 0.5), rejection sampling.

    Returns:
        positions  : (N, 3) float32 array in [0,1]^3
        assignments: (N,)   int array, index of nearest emitter
    """
    rng = np.random.default_rng(seed)
    positions   = []
    assignments = []
    attempts    = 0
    max_attempts = num_particles * 200

    while len(positions) < num_particles and attempts < max_attempts:
        attempts += 1
        p = rng.random(3).astype(np.float32)

        # Reject if outside sphere radius 0.85 centred at 0.5
        if np.sum((p - 0.5)**2) > 0.85**2:
            continue

        # Assign to nearest emitter (in normalised grid space)
        dists   = np.linalg.norm(emitter_positions_norm - p, axis=1)
        nearest = int(np.argmin(dists))

        positions.append(p)
        assignments.append(nearest)

    if len(positions) < num_particles:
        print(f"Warning: only generated {len(positions)} of {num_particles} "
              f"requested particles after {attempts} attempts.",
              file=sys.stderr)
    else:
        print(f"Generated {len(positions)} particles.", file=sys.stderr)

    return np.array(positions, dtype=np.float32), np.array(assignments, dtype=np.int32)


def build_density_grids(positions: np.ndarray,
                        assignments: np.ndarray,
                        nx: int, ny: int, nz: int,
                        particle_radius: float,
                        particle_peak: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build three separate float density grids, one per colour channel.
    Returns (density_r, density_g, density_b), each shape (nz, ny, nx).
    """
    grids = [np.zeros((nz, ny, nx), dtype=np.float32) for _ in range(3)]

    for i, (pos, emitter) in enumerate(zip(positions, assignments)):
        # Convert normalised [0,1] -> voxel coordinates
        vox = pos * np.array([nx-1, ny-1, nz-1], dtype=np.float32)
        paint_blob(grids[emitter], vox, particle_radius, particle_peak)

        if (i+1) % 50 == 0:
            print(f"  Painted {i+1}/{len(positions)} particles...", file=sys.stderr)

    return grids[0], grids[1], grids[2]


def interleave_rgb(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Interleave three (nz,ny,nx) grids into a flat RGB array.
    pbrt expects: [R0,G0,B0, R1,G1,B1, ...] in x-fastest (C) order.
    """
    flat_r = r.ravel()
    flat_g = g.ravel()
    flat_b = b.ravel()
    interleaved = np.empty(len(flat_r) * 3, dtype=np.float32)
    interleaved[0::3] = flat_r
    interleaved[1::3] = flat_g
    interleaved[2::3] = flat_b
    return interleaved


def float_array_to_pbrt(values: np.ndarray, indent: int = 8, per_line: int = 8) -> str:
    """Format a float array as pbrt inline values, per_line numbers per line."""
    pad  = " " * indent
    lines = []
    for i in range(0, len(values), per_line):
        chunk = values[i:i+per_line]
        lines.append(pad + " ".join(f"{v:.6g}" for v in chunk))
    return "\n" + "\n".join(lines) + "\n" + pad


# =============================================================================
# Scene file writer
# =============================================================================

def write_scene(cfg: dict,
                sigma_s_rgb: np.ndarray,
                sigma_a_rgb: np.ndarray,
                num_particles: int) -> None:

    out_path = Path(cfg["out"])
    r        = cfg["enclosing_radius"]

    lines = []
    a = lines.append   # shorthand

    a("# =============================================================")
    a("# Pointillist Volume - Version 4 (rgbgrid medium)")
    a("# Generated by generate_density.py")
    a(f"# Grid: {cfg['nx']} x {cfg['ny']} x {cfg['nz']}")
    a(f"# Particles: {num_particles}")
    a(f"# Particle radius (voxels): {cfg['particle_radius']}")
    a("# =============================================================")
    a("")
    a('Film "rgb"')
    a('    "integer xresolution" [1920]')
    a('    "integer yresolution" [1920]')
    a(f'    "string filename" ["{out_path.stem}.png"]')
    a("")
    a('Sampler "halton"')
    a('    "integer pixelsamples" [128]')
    a("")
    a('Integrator "volpath"')
    a('    "integer maxdepth" [32]')
    a("")
    a(f"LookAt  0 0 {cfg['camera_z']}   0 0 0   0 1 0")
    a('Camera "perspective"')
    a('    "float fov" [45]')
    a("")
    a("WorldBegin")
    a("")

    # Medium
    a('    # ----------------------------------------------------------')
    a('    # RGB density grid')
    a('    # Each channel (R/G/B) scatters only its own wavelength.')
    a('    # ----------------------------------------------------------')
    a('    MakeNamedMedium "particles"')
    a('        "string type"   [ "rgbgrid" ]')
    a(f'        "float scale"   [ {cfg["medium_scale"]} ]')
    a(f'        "float g"       [ {cfg["g"]} ]')
    a(f'        "integer nx"    [ {cfg["nx"]} ]')
    a(f'        "integer ny"    [ {cfg["ny"]} ]')
    a(f'        "integer nz"    [ {cfg["nz"]} ]')
    a(f'        "point3 p0"     [ {-r} {-r} {-r} ]')
    a(f'        "point3 p1"     [ {r} {r} {r} ]')

    # sigma_s
    a('        "rgb sigma_s" [' + float_array_to_pbrt(sigma_s_rgb) + ']')

    # sigma_a
    a('        "rgb sigma_a" [' + float_array_to_pbrt(sigma_a_rgb) + ']')
    a("")

    # Enclosing sphere
    a('    # ----------------------------------------------------------')
    a('    # Enclosing sphere — medium boundary, invisible to rays')
    a('    # ----------------------------------------------------------')
    a('    AttributeBegin')
    a('        MediumInterface "particles" ""')
    a('        Material "interface"')
    a(f'        Shape "sphere" "float radius" [{r}]')
    a('    AttributeEnd')
    a("")

    # Emitters
    intensity = cfg["emitter_intensity"]
    er        = cfg["emitter_radius"]

    for e, (pos, color, name) in enumerate(zip(EMITTER_POSITIONS,
                                                EMITTER_COLORS,
                                                EMITTER_NAMES)):
        rgb_L    = f"{color[0]*intensity} {color[1]*intensity} {color[2]*intensity}"
        rgb_refl = f"{color[0]} {color[1]} {color[2]}"
        a(f'    # {name} emitter')
        a('    AttributeBegin')
        a(f'        Translate {pos[0]} {pos[1]} {pos[2]}')
        a('        AreaLightSource "diffuse"')
        a(f'            "rgb L" [ {rgb_L} ]')
        a('        Material "diffuse"')
        a(f'            "rgb reflectance" [ {rgb_refl} ]')
        a(f'        Shape "sphere" "float radius" [{er}]')
        a('    AttributeEnd')
        a("")

    a("# end of scene")

    scene_text = "\n".join(lines)
    out_path.write_text(scene_text)
    print(f"Scene written to: {out_path}", file=sys.stderr)


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> dict:
    parser = argparse.ArgumentParser(
        description="Generate a pbrt-v4 rgbgrid pointillist volume scene."
    )
    parser.add_argument("--nx",               type=int,   default=DEFAULTS["nx"])
    parser.add_argument("--ny",               type=int,   default=DEFAULTS["ny"])
    parser.add_argument("--nz",               type=int,   default=DEFAULTS["nz"])
    parser.add_argument("--num-particles",    type=int,   default=DEFAULTS["num_particles"])
    parser.add_argument("--particle-radius",  type=float, default=DEFAULTS["particle_radius"],
                        help="Particle radius in voxels")
    parser.add_argument("--particle-peak",    type=float, default=DEFAULTS["particle_peak"])
    parser.add_argument("--medium-scale",     type=float, default=DEFAULTS["medium_scale"])
    parser.add_argument("--g",                type=float, default=DEFAULTS["g"],
                        help="Scattering asymmetry (0=isotropic)")
    parser.add_argument("--emitter-intensity",type=float, default=DEFAULTS["emitter_intensity"])
    parser.add_argument("--emitter-radius",   type=float, default=DEFAULTS["emitter_radius"])
    parser.add_argument("--enclosing-radius", type=float, default=DEFAULTS["enclosing_radius"])
    parser.add_argument("--camera-z",         type=float, default=DEFAULTS["camera_z"])
    parser.add_argument("--seed",             type=int,   default=DEFAULTS["seed"])
    parser.add_argument("--out",              type=str,   default=DEFAULTS["out"],
                        help="Output .pbrt filename")

    args = parser.parse_args()
    return vars(args)


# =============================================================================
# Main
# =============================================================================

def main():
    cfg = parse_args()

    nx, ny, nz = cfg["nx"], cfg["ny"], cfg["nz"]
    r          = cfg["enclosing_radius"]

    print("Generating particles...", file=sys.stderr)

    # Normalise emitter positions to [0,1]^3 grid space
    emitter_norm = world_to_grid_norm(EMITTER_POSITIONS, r)

    positions, assignments = generate_particles(
        num_particles      = cfg["num_particles"],
        enclosing_radius   = r,
        emitter_positions_norm = emitter_norm,
        seed               = cfg["seed"],
    )

    print("Building density grids...", file=sys.stderr)

    density_r, density_g, density_b = build_density_grids(
        positions        = positions,
        assignments      = assignments,
        nx               = nx,
        ny               = ny,
        nz               = nz,
        particle_radius  = cfg["particle_radius"],
        particle_peak    = cfg["particle_peak"],
    )

    print("Interleaving RGB channels...", file=sys.stderr)

    sigma_s_rgb = interleave_rgb(density_r, density_g, density_b)

    # Very low absorption — let light travel through the volume
    sigma_a_rgb = sigma_s_rgb * 0.002

    print("Writing scene file...", file=sys.stderr)

    write_scene(
        cfg          = cfg,
        sigma_s_rgb  = sigma_s_rgb,
        sigma_a_rgb  = sigma_a_rgb,
        num_particles = len(positions),
    )


if __name__ == "__main__":
    main()
