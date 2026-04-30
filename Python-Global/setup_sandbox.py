import os
import random
from datetime import datetime

# ==========================================
# 1. AUTO-PATHING (Fixes the Redirect Issue)
# ==========================================
# Find where THIS script is, then go up one level to the project root
script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)
project_root = os.path.dirname(script_dir)

# Define absolute paths for scenes and renders
scenes_dir = os.path.join(project_root, "scenes")
renders_dir = os.path.join(project_root, "renders")

# Ensure the folders exist in the new project
os.makedirs(scenes_dir, exist_ok=True)
os.makedirs(renders_dir, exist_ok=True)

# ==========================================
# 2. SCALARS (The Hand-Input Form)
# ==========================================
samples = 64
res_x, res_y = 1280, 720
camera_eye = [12, 5, 12]
look_at = [0, 1, 0]

# Fog Density [R, G, B]
fog_density = [0.25, 0.25, 0.25] 
sphere_count = 15

# Timestamps for unique file versioning
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_png = os.path.join(renders_dir, f"fog_v4_{timestamp}.png")
scene_file = os.path.join(scenes_dir, f"fog_scene_{timestamp}.pbrt")

# ==========================================
# 3. THE BLUEPRINT CONSTRUCTION (v4)
# ==========================================
pbrt_content = f"""
Integrator "volpath"
Sampler "halton" "integer pixelsamples" [{samples}]
Film "rgb" "string filename" ["{output_png}"]
     "integer xresolution" [{res_x}] "integer yresolution" [{res_y}]

LookAt {camera_eye[0]} {camera_eye[1]} {camera_eye[2]}  {look_at[0]} {look_at[1]} {look_at[2]}  0 1 0
Camera "perspective" "float fov" [45]

WorldBegin
    # --- LIGHTING ---
    AttributeBegin
        LightSource "point" "point3 from" [0 15 0] "rgb I" [800 800 800]
    AttributeEnd

    # --- MEDIA (The Fog) ---
    MakeNamedMedium "atmosphere" "string type" ["homogeneous"] 
                    "rgb sigma_s" [{fog_density[0]} {fog_density[1]} {fog_density[2]}]
    MediumInterface "atmosphere" ""

    # --- GEOMETRY ---
"""

# Procedural Geometry Loop
for i in range(sphere_count):
    x = random.uniform(-7, 7)
    z = random.uniform(-7, 7)
    radius = random.uniform(0.5, 1.2)
    
    pbrt_content += f"""
    AttributeBegin
        Translate {x} {radius} {z}
        Material "dielectric" 
        Shape "sphere" "float radius" [{radius}]
    AttributeEnd
    """

# No WorldEnd for v4

# ==========================================
# 4. SAVE, RENDER, AND AUTO-REVEAL
# ==========================================
with open(scene_file, "w") as f:
    f.write(pbrt_content)

print(f"\n[SUCCESS] Blueprint saved: {scene_file}")
print(f"[STATUS] RTX 2070 rendering to: {output_png}")

# Force the image to open in VS Code once the render task finishes
# This uses the absolute path to ensure it finds the right file
os.system(f"code -r {output_png} || xdg-open {output_png} &")