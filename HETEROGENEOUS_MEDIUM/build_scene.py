#!/usr/bin/env python3
"""
gen_rgbgrid_poc.py

Generates rgbgrid_medium_XXXXXX.pbrt containing only the
MakeNamedMedium block for use with rgbgrid_poc_XXXXXX.pbrt.

The volume is divided into three zones along X:
  Left  : red scattering
  Centre: green scattering
  Right : blue scattering

Edit the parameters below to experiment with zone widths,
blend, and scattering strength.
"""

# ---------------------------------------------------------------------------
# PARAMETERS — edit these
# ---------------------------------------------------------------------------

NX = 16           # grid resolution X
NY = 16           # grid resolution Y
NZ = 16           # grid resolution Z

SIGMA_S_PEAK = 3.0   # peak scattering coefficient
SIGMA_A      = 0.02  # absorption (uniform, all channels)
BLEND_WIDTH  = 0.2   # zone blend width [0-1], larger = softer transitions

OUTPUT = "rgbgrid_medium_XXXXXX.pbrt"

# ---------------------------------------------------------------------------


def build_rgbgrid():
    sigma_s = []
    sigma_a = []

    for k in range(NZ):
        for j in range(NY):
            for i in range(NX):
                t = (i + 0.5) / NX   # normalised X [0, 1]

                left_centre  = 1.0 / 6.0
                mid_centre   = 3.0 / 6.0
                right_centre = 5.0 / 6.0

                def weight(pos, centre, width):
                    return max(0.0, 1.0 - abs(pos - centre) / width)

                w_r = weight(t, left_centre,  BLEND_WIDTH)
                w_g = weight(t, mid_centre,   BLEND_WIDTH)
                w_b = weight(t, right_centre, BLEND_WIDTH)

                sigma_s += [w_r * SIGMA_S_PEAK,
                            w_g * SIGMA_S_PEAK,
                            w_b * SIGMA_S_PEAK]
                sigma_a += [SIGMA_A, SIGMA_A, SIGMA_A]

    return sigma_s, sigma_a


def fmt(values, per_line=9):
    lines = []
    for i in range(0, len(values), per_line):
        chunk = values[i:i + per_line]
        lines.append("        " + " ".join(f"{v:.4f}" for v in chunk))
    return "\n".join(lines)


def main():
    print(f"Building {NX}x{NY}x{NZ} rgbgrid...")
    sigma_s, sigma_a = build_rgbgrid()

    block = f"""\
MakeNamedMedium "rgb_vol"
    "string type"   [ "rgbgrid" ]
    "integer nx"    [ {NX} ]
    "integer ny"    [ {NY} ]
    "integer nz"    [ {NZ} ]
    "point3 p0"     [ -1.5 -1.5 -1.5 ]
    "point3 p1"     [  1.5  1.5  1.5 ]
    "float g"       [ 0.0 ]
    "rgb sigma_a"   [
{fmt(sigma_a)}
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
