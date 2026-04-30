import os
from datetime import datetime

# 1. PATHS
project_root = "/home/rpf4/my-pbrt-projects/02_FOG_SCENES"
scenes_dir = "/home/rpf4/my-pbrt-projects/02_FOG_SCENES/scenes"
renders_dir = "/home/rpf4/my-pbrt-projects/02_FOG_SCENES/renders"

os.makedirs(scenes_dir, exist_ok=True)
os.makedirs(renders_dir, exist_ok=True)

# 2. FILE NAMES
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_png = f"{renders_dir}/baseline_{timestamp}.png"
scene_file = f"{scenes_dir}/sandbox_render.pbrt"

# 3. THE "ONE LIGHT, ONE SPHERE" BLUEPRINT
pbrt_content = f"""
Integrator "path"
Sampler "halton" "integer pixelsamples" [16]
Film "rgb" "string filename" ["{output_png}"]
     "integer xresolution" [640] "integer yresolution" [480]

# Camera looking straight at the center (0,0,0) from 10 units away
LookAt 0 0 10  0 0 0  0 1 0
Camera "perspective" "float fov" [45]

WorldBegin
    # One bright light source sitting right behind/above the camera
    AttributeBegin
        LightSource "point" "point3 from" [5 5 10] "rgb I" [5000 5000 5000]
    AttributeEnd

    # One white sphere at the center of the world
    AttributeBegin
        Material "diffuse" "rgb reflectance" [0.8 0.8 0.8]
        Translate 0 0 0
        Shape "sphere" "float radius" [3]
    AttributeEnd
"""

with open(scene_file, "w") as f:
    f.write(pbrt_content)

print(f"Scene file created at: {scene_file}")