#!/usr/bin/env python3
"""
gen_rgbgrid_poc.py

Generates rgbgrid_medium_XXXXXX.pbrt containing the MakeNamedMedium block.

Zones are defined by wavelength, position, width and strength.
Wavelengths are converted to approximate RGB scattering coefficients.
Any number of zones can be defined.
Zones can run along X, Y, or Z axis.
"""

# ---------------------------------------------------------------------------
# GRID PARAMETERS
# ---------------------------------------------------------------------------

#NX = 64
#NY = 64
#NZ = 64
NX = 128
NY = 128
NZ = 128

AXIS = "X"          # Zone axis: "X", "Y", or "Z"

#SIGMA_A = 0.02      # Absorption — uniform across all voxels
SIGMA_A = 2.4

OUTPUT = "rgbgrid_medium_YYYYYY.pbrt"

# Volume world-space bounds — must match p0/p1 in scene file
WORLD_MIN = -1.5
WORLD_MAX =  1.5

# ---------------------------------------------------------------------------
# ZONE DEFINITIONS
# Each zone:
#   position   -- normalised position along AXIS [0.0, 1.0]
#   wavelength -- peak wavelength in nm (approx 380-700)
#   width      -- blend width [0.0, 1.0], larger = softer edges
#   strength   -- peak sigma_s value for this zone
# ---------------------------------------------------------------------------

ZONES = [
    #{ "position": 0.2, "wavelength": 650, "width": 0.20, "strength": 1.0 },  # red — low scatter, deep penetration
    #{ "position": 0.4, "wavelength": 580, "width": 0.20, "strength": 2.0 },  # orange/yellow
    #{ "position": 0.6, "wavelength": 510, "width": 0.20, "strength": 3.5 },  # green
    #{ "position": 0.8, "wavelength": 450, "width": 0.20, "strength": 6.0 },  # blue — high scatter, surface glow
    { "position": 0.2, "wavelength": 650, "width": 0.20, "strength": 12.0 },  # red — low scatter, deep penetration
    { "position": 0.4, "wavelength": 580, "width": 0.20, "strength": 12.0 },  # orange/yellow
    { "position": 0.6, "wavelength": 510, "width": 0.20, "strength": 12.5 },  # green
    { "position": 0.8, "wavelength": 450, "width": 0.20, "strength": 12.0 },  # blue — high scatter, surface glow
]


# ---------------------------------------------------------------------------
# WAVELENGTH TO RGB
# Approximate conversion of a peak wavelength to an RGB triple.
# Based on the CIE color matching functions, simplified for scattering use.
# ---------------------------------------------------------------------------

def wavelength_to_rgb(wl):
    """
    Convert a wavelength in nm to an approximate linear RGB triple.
    Returns (r, g, b) each in [0, 1].
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

    # Intensity falloff at edges of visible spectrum
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

def build_rgbgrid():
    sigma_s = []
    sigma_a_flat = []

    for k in range(NZ):
        for j in range(NY):
            for i in range(NX):
                # Normalised position along chosen axis
                if   AXIS == "X": t = (i + 0.5) / NX
                elif AXIS == "Y": t = (j + 0.5) / NY
                else:             t = (k + 0.5) / NZ

                # Accumulate contributions from all zones
                sr, sg, sb = 0.0, 0.0, 0.0
                for zone in ZONES:
                    d = abs(t - zone["position"])
                    w = max(0.0, 1.0 - d / zone["width"])
                    rgb = wavelength_to_rgb(zone["wavelength"])
                    sr += w * zone["strength"] * rgb[0]
                    sg += w * zone["strength"] * rgb[1]
                    sb += w * zone["strength"] * rgb[2]

                sigma_s     += [sr, sg, sb]
                sigma_a_flat += [SIGMA_A, SIGMA_A, SIGMA_A]

    return sigma_s, sigma_a_flat


# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------

def fmt(values, per_line=9):
    lines = []
    for i in range(0, len(values), per_line):
        chunk = values[i:i + per_line]
        lines.append("        " + " ".join(f"{v:.5f}" for v in chunk))
    return "\n".join(lines)


def main():
    print(f"Building {NX}x{NY}x{NZ} rgbgrid  axis={AXIS}  zones={len(ZONES)}")
    for z in ZONES:
        rgb = wavelength_to_rgb(z["wavelength"])
        print(f"  {z['wavelength']}nm  pos={z['position']}  "
              f"width={z['width']}  strength={z['strength']}  "
              f"rgb=({rgb[0]:.3f}, {rgb[1]:.3f}, {rgb[2]:.3f})")

    sigma_s, sigma_a_flat = build_rgbgrid()

    block = f"""\
MakeNamedMedium "rgb_vol"
    "string type"   [ "rgbgrid" ]
    "integer nx"    [ {NX} ]
    "integer ny"    [ {NY} ]
    "integer nz"    [ {NZ} ]
    "point3 p0"     [ {WORLD_MIN} {WORLD_MIN} {WORLD_MIN} ]
    "point3 p1"     [ {WORLD_MAX} {WORLD_MAX} {WORLD_MAX} ]
    "float g"       [ 0.0 ]
    "rgb sigma_a"   [
{fmt(sigma_a_flat)}
    ]
    "rgb sigma_s"   [
{fmt(sigma_s)}
    ]
"""

    with open(OUTPUT, "w") as f:
        f.write(block)
    print(f"Written: {OUTPUT}")


if __name__ == "__main__":
    main()
