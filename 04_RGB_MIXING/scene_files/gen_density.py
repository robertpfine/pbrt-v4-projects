#!/usr/bin/env python3
"""
gen_density.py

Generates a 3D Perlin noise density grid and writes it as a raw binary
file for consumption by make_nvdb.

Output format:
  - 3 x int32  : nx, ny, nz
  - nx*ny*nz x float32 : density values in [0,1], x-fastest order

Usage:
  python gen_density.py --nx 32 --ny 32 --nz 32 --scale 3.0 --out density.bin
"""

import argparse
import math
import random
import struct


# ---------------------------------------------------------------------------
# Minimal self-contained Perlin noise
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
    return (_lerp(y1, y2, w) + 1.0) * 0.5


def main():
    p = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--nx", type=int, default=32)
    p.add_argument("--ny", type=int, default=32)
    p.add_argument("--nz", type=int, default=32)
    p.add_argument("--scale", type=float, default=3.0,
                   help="Noise spatial frequency (default: 3.0)")
    p.add_argument("--out", default="density.bin",
                   help="Output binary file (default: density.bin)")
    args = p.parse_args()

    nx, ny, nz = args.nx, args.ny, args.nz
    total = nx * ny * nz
    print(f"Generating {nx}x{ny}x{nz} density grid ({total} voxels)...")

    values = []
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                x = (i + 0.5) / nx * args.scale
                y = (j + 0.5) / ny * args.scale
                z = (k + 0.5) / nz * args.scale
                values.append(noise3(x, y, z))

    with open(args.out, "wb") as f:
        f.write(struct.pack("iii", nx, ny, nz))
        f.write(struct.pack(f"{total}f", *values))

    import os
    size_kb = os.path.getsize(args.out) // 1024
    print(f"Written: {args.out}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
