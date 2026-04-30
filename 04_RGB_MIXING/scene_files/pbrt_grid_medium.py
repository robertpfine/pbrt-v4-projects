#!/usr/bin/env python3
"""
pbrt_grid_medium.py

Generates a pbrt-v4 scene file containing a grid-based participating medium.

Two modes:

  uniformgrid  -- one scalar density per voxel, driven by Perlin noise.
                  sigma_a and sigma_s are single RGB values that apply
                  uniformly across the whole volume.
                  pbrt computes per-voxel: effective_scatter = density * sigma_s

  rgbgrid      -- one RGB triple for sigma_s and sigma_a per voxel.
                  A single Perlin noise value scales the base RGB you
                  provide at each voxel.  Different regions of the volume
                  can scatter different colours independently.

Usage
-----
  # uniformgrid: noisy density, uniform blue scattering
  python pbrt_grid_medium.py --type uniformgrid \\
      --sigma_s 0.2 0.2 2.0 --sigma_a 0.05 0.05 0.05

  # rgbgrid: per-voxel RGB scattering driven by noise
  python pbrt_grid_medium.py --type rgbgrid \\
      --base_s 1.0 0.5 0.2 --base_a 0.05 0.05 0.05
"""

import argparse
import math
import random
import textwrap
from pathlib import Path


# ---------------------------------------------------------------------------
# Minimal self-contained Perlin noise  (no external dependencies)
# ---------------------------------------------------------------------------

_PERM = list(range(256))
random.seed(42)
random.shuffle(_PERM)
_PERM *= 2


def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def _lerp(a, b, t):
    return a + t * (b - a)


def _grad(h, x, y, z):
    h &= 15
    u = x if h < 8 else y
    v = y if h < 4 else (x if h in (12, 14) else z)
    return (u if h & 1 == 0 else -u) + (v if h & 2 == 0 else -v)


def noise3(x, y, z):
    """Perlin noise, remapped to [0, 1]."""
    xi = int(math.floor(x)) & 255
    yi = int(math.floor(y)) & 255
    zi = int(math.floor(z)) & 255
    xf, yf, zf = x - math.floor(x), y - math.floor(y), z - math.floor(z)
    u, v, w = _fade(xf), _fade(yf), _fade(zf)
    p = _PERM
    aaa = p[p[p[xi  ] + yi  ] + zi  ];  baa = p[p[p[xi+1] + yi  ] + zi  ]
    aba = p[p[p[xi  ] + yi+1] + zi  ];  bba = p[p[p[xi+1] + yi+1] + zi  ]
    aab = p[p[p[xi  ] + yi  ] + zi+1];  bab = p[p[p[xi+1] + yi  ] + zi+1]
    abb = p[p[p[xi  ] + yi+1] + zi+1];  bbb = p[p[p[xi+1] + yi+1] + zi+1]
    x1 = _lerp(_grad(aaa, xf,   yf,   zf  ), _grad(baa, xf-1, yf,   zf  ), u)
    x2 = _lerp(_grad(aba, xf,   yf-1, zf  ), _grad(bba, xf-1, yf-1, zf  ), u)
    y1 = _lerp(x1, x2, v)
    x1 = _lerp(_grad(aab, xf,   yf,   zf-1), _grad(bab, xf-1, yf,   zf-1), u)
    x2 = _lerp(_grad(abb, xf,   yf-1, zf-1), _grad(bbb, xf-1, yf-1, zf-1), u)
    y2 = _lerp(x1, x2, v)
    return (_lerp(y1, y2, w) + 1.0) * 0.5   # remap [-1,1] -> [0,1]


# ---------------------------------------------------------------------------
# Grid builders
# ---------------------------------------------------------------------------

def build_uniformgrid_density(nx, ny, nz, scale):
    """
    Returns a flat list of nx*ny*nz scalar density values in [0, 1].
    Ordering is x-fastest (pbrt convention: iterate z, then y, then x).
    """
    values = []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                x = (i + 0.5) / nx * scale
                y = (j + 0.5) / ny * scale
                z = (k + 0.5) / nz * scale
                values.append(noise3(x, y, z))
    return values


def build_rgbgrid_arrays(nx, ny, nz, scale, base_s, base_a):
    """
    Returns (sigma_s_flat, sigma_a_flat).
    Each is a flat list of nx*ny*nz*3 floats (R,G,B interleaved per voxel).
    A single noise value per voxel scales the provided base RGB triples.
    """
    sigma_s, sigma_a = [], []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                x = (i + 0.5) / nx * scale
                y = (j + 0.5) / ny * scale
                z = (k + 0.5) / nz * scale
                d = noise3(x, y, z)
                sigma_s += [d * base_s[0], d * base_s[1], d * base_s[2]]
                sigma_a += [d * base_a[0], d * base_a[1], d * base_a[2]]
    return sigma_s, sigma_a


# ---------------------------------------------------------------------------
# pbrt serialisers
# ---------------------------------------------------------------------------

def _fmt(values, per_line=8):
    """Format a flat float list as indented pbrt array rows."""
    lines = []
    for i in range(0, len(values), per_line):
        chunk = values[i:i + per_line]
        lines.append("        " + " ".join(f"{v:.6f}" for v in chunk))
    return "\n".join(lines)


def medium_uniformgrid(name, nx, ny, nz, density, sigma_a, sigma_s, g, p0, p1):
    sa  = " ".join(str(v) for v in sigma_a)
    ss  = " ".join(str(v) for v in sigma_s)
    p0s = " ".join(str(v) for v in p0)
    p1s = " ".join(str(v) for v in p1)
    return textwrap.dedent(f"""\
        MakeNamedMedium "{name}"
            "string type"   [ "uniformgrid" ]
            "integer nx"    [ {nx} ]
            "integer ny"    [ {ny} ]
            "integer nz"    [ {nz} ]
            "point3 p0"     [ {p0s} ]
            "point3 p1"     [ {p1s} ]
            "rgb sigma_a"   [ {sa} ]
            "rgb sigma_s"   [ {ss} ]
            "float g"       [ {g} ]
            "float density" [
        {_fmt(density)}
            ]
        """)


def medium_rgbgrid(name, nx, ny, nz, sigma_a, sigma_s, g, p0, p1):
    p0s = " ".join(str(v) for v in p0)
    p1s = " ".join(str(v) for v in p1)
    return textwrap.dedent(f"""\
        MakeNamedMedium "{name}"
            "string type"   [ "rgbgrid" ]
            "integer nx"    [ {nx} ]
            "integer ny"    [ {ny} ]
            "integer nz"    [ {nz} ]
            "point3 p0"     [ {p0s} ]
            "point3 p1"     [ {p1s} ]
            "float g"       [ {g} ]
            "rgb sigma_a"   [
        {_fmt(sigma_a, per_line=9)}
            ]
            "rgb sigma_s"   [
        {_fmt(sigma_s, per_line=9)}
            ]
        """)


def bounding_box(name, p0, p1):
    """Null-material box that marks the medium boundary."""
    p0s = " ".join(str(v) for v in p0)
    p1s = " ".join(str(v) for v in p1)
    return textwrap.dedent(f"""\
        AttributeBegin
            MediumInterface "{name}" ""
            Material ""
            Shape "box"
                "point3 p0" [ {p0s} ]
                "point3 p1" [ {p1s} ]
        AttributeEnd
        """)


def full_scene(medium_block, box_block, resolution, spp):
    return textwrap.dedent(f"""\
        # pbrt-v4 grid medium scene
        # pbrt --gpu --outfile out.exr scene.pbrt

        LookAt  3 2 3   0 0 0   0 1 0
        Camera "perspective" "float fov" [ 40 ]

        Sampler "zsobol" "integer pixelsamples" [ {spp} ]
        Film "rgb"
            "string filename"     [ "out.exr" ]
            "integer xresolution" [ {resolution} ]
            "integer yresolution" [ {resolution} ]

        WorldBegin

        LightSource "distant"
            "point3 from" [ 5 8 5 ]
            "blackbody L" [ 6500 ]
            "float scale" [ 3.0 ]

        LightSource "infinite"
            "rgb L" [ 0.15 0.18 0.22 ]

        {medium_block.rstrip()}

        {box_block.rstrip()}

        """).lstrip()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--type", choices=["uniformgrid", "rgbgrid"], default="uniformgrid",
                   help="Medium type (default: uniformgrid)")

    # Grid resolution
    p.add_argument("--nx", type=int, default=32)
    p.add_argument("--ny", type=int, default=32)
    p.add_argument("--nz", type=int, default=32)
    p.add_argument("--noise-scale", type=float, default=3.0,
                   help="Spatial frequency of Perlin noise (default: 3.0)")

    # uniformgrid: fixed coefficients
    p.add_argument("--sigma_s", nargs=3, type=float, default=[1.0, 1.0, 1.0],
                   metavar=("R", "G", "B"),
                   help="Uniform scattering coefficient for uniformgrid (default: 1 1 1)")
    p.add_argument("--sigma_a", nargs=3, type=float, default=[0.05, 0.05, 0.05],
                   metavar=("R", "G", "B"),
                   help="Uniform absorption coefficient for uniformgrid (default: 0.05 0.05 0.05)")

    # rgbgrid: per-voxel base colours
    p.add_argument("--base_s", nargs=3, type=float, default=[1.0, 1.0, 1.0],
                   metavar=("R", "G", "B"),
                   help="Base scattering colour for rgbgrid, scaled per-voxel by noise (default: 1 1 1)")
    p.add_argument("--base_a", nargs=3, type=float, default=[0.05, 0.05, 0.05],
                   metavar=("R", "G", "B"),
                   help="Base absorption colour for rgbgrid, scaled per-voxel by noise (default: 0.05 0.05 0.05)")

    # Shared
    p.add_argument("--g", type=float, default=0.0,
                   help="Phase function asymmetry [-1, 1] (default: 0.0)")
    p.add_argument("--p0", nargs=3, type=float, default=[-1.0, -1.0, -1.0],
                   metavar=("X", "Y", "Z"), help="Volume min corner (default: -1 -1 -1)")
    p.add_argument("--p1", nargs=3, type=float, default=[ 1.0,  1.0,  1.0],
                   metavar=("X", "Y", "Z"), help="Volume max corner (default: 1 1 1)")
    p.add_argument("--name", default="vol",
                   help="Medium name used in MakeNamedMedium (default: vol)")

    # Output
    p.add_argument("--outfile", default="scene.pbrt")
    p.add_argument("--resolution", type=int, default=512,
                   help="Image resolution in pixels (default: 512)")
    p.add_argument("--spp", type=int, default=256,
                   help="Samples per pixel (default: 256)")
    p.add_argument("--snippet-only", action="store_true",
                   help="Write only the MakeNamedMedium block, no scene boilerplate")

    args = p.parse_args()
    nx, ny, nz = args.nx, args.ny, args.nz
    p0, p1 = tuple(args.p0), tuple(args.p1)

    print(f"type={args.type}  grid={nx}x{ny}x{nz}  noise_scale={args.noise_scale}")

    if args.type == "uniformgrid":
        density = build_uniformgrid_density(nx, ny, nz, args.noise_scale)
        med = medium_uniformgrid(args.name, nx, ny, nz, density,
                                 args.sigma_a, args.sigma_s, args.g, p0, p1)
    else:
        sigma_s, sigma_a = build_rgbgrid_arrays(
            nx, ny, nz, args.noise_scale, args.base_s, args.base_a)
        med = medium_rgbgrid(args.name, nx, ny, nz, sigma_a, sigma_s,
                             args.g, p0, p1)

    box = bounding_box(args.name, p0, p1)
    output = med if args.snippet_only else full_scene(med, box, args.resolution, args.spp)

    out = Path(args.outfile)
    out.write_text(output)
    print(f"written: {out}  ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
