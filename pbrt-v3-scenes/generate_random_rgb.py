# generate_random_rgb.py
# Save to: C:\Users\rpf4\PBRT\test_scenes\generate_random_rgb.py

import random
import sys
from datetime import datetime


def generate_scene(num_spheres=50, description="random_rgb", seed=None):
    if seed is not None:
        random.seed(seed)

    # Generate timestamp and paths
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    generated_at = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
    pair_id = f"{description}_{timestamp}"
    output_dir = "G:/My Drive/wipImages/PBRT/renders_and_scenes"
    output_png = f"{output_dir}/{pair_id}_render.png"
    output_pbrt = f"{output_dir}/{pair_id}_scene.pbrt"


    scene = f"""# {num_spheres} Random RGB Emissives in Fog
# Generated scene

# ============================================================
# Auto-generated PBRT-v3 scene
# Generated on: {generated_at}
# Pair ID: {pair_id}
# Render output: {output_png}
# ============================================================

LookAt 0 2 -12   0 1 0   0 1 0
Camera "perspective" "float fov" [45]

Film "image"
    "string filename" "{output_png}"
    "integer xresolution" [800]
    "integer yresolution" [600]

Sampler "halton" "integer pixelsamples" [256]
Integrator "volpath" "integer maxdepth" [64]

MakeNamedMedium "fog"
    "string type" "homogeneous"
    "rgb sigma_a" [0.0 0.0 0.0]
    "rgb sigma_s" [0.12 0.12 0.12]
    "float g" [0.0]

#MediumInterface "" "fog"
MediumInterface "" ""

WorldBegin

#MediumInterface "fog" "fog"

"""

    colors = [
        ("red",   "15 0 0"),
        ("green", "0 15 0"),
        ("blue",  "0 0 15")
    ]

    for i in range(num_spheres):
        x = random.uniform(-5, 5)
        y = random.uniform(-1, 5)
        z = random.uniform(-5, 5)
        color_name, color_rgb = random.choice(colors)

        scene += f"""# Sphere {i+1} ({color_name})
AttributeBegin
    Translate {x:.2f} {y:.2f} {z:.2f}
    AreaLightSource "diffuse" "rgb L" [{color_rgb}]
    Material "matte" "rgb Kd" [0.1 0.1 0.1]
    Shape "sphere" "float radius" [0.05]
AttributeEnd

"""

    scene += """# Fog boundary
AttributeBegin
    MediumInterface "fog" ""
    Material "none"
    Shape "sphere" "float radius" [15]
AttributeEnd

# Ground
#AttributeBegin
#    Material "matte" "rgb Kd" [0.2 0.2 0.2]
#    Shape "trianglemesh"
#        "integer indices" [0 1 2  0 2 3]
#        "point P" [-20 0 -20   20 0 -20   20 0 20   -20 0 20]
#AttributeEnd

WorldEnd
"""

    with open(output_pbrt, "w") as f:
        f.write(scene)

    print(f"Generated {output_pbrt} with {num_spheres} spheres")
    return output_pbrt


if __name__ == "__main__":
    import sys

    num = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    out = sys.argv[2] if len(sys.argv) > 2 else "random_rgb_5000.pbrt"
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else None

    generate_scene(num, out, seed)