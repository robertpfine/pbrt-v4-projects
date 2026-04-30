import sys
import os

# 1. Tell Python where to find your Global Templates
sys.path.append(os.path.expanduser("~/my-pbrt-projects/GLOBAL_TEMPLATES/python"))

# 2. Import your Master Template logic
from pbrt_master_template import create_scene_with_metadata

# 3. Define the "Meat" of your scene
my_geometry = """
    AttributeBegin
        Material "dielectric" "float eta" [1.5]
        Translate 0 1 0
        Shape "sphere" "float radius" [1]
    AttributeEnd

    AttributeBegin
        Material "diffuse" "rgb reflectance" [0.4 0.5 0.4]
        Shape "trianglemesh" 
            "integer indices" [0 1 2 0 2 3] 
            "point3 P" [-10 0 -10  10 0 -10  10 0 10  -10 0 10]
    AttributeEnd
"""

print("Starting render script...")

# 4. Define the path so the computer knows WHERE to save
project_path = os.path.expanduser("~/my-pbrt-projects/01_MY_FIRST_GPU_RENDER")

# 5. Execute the template
create_scene_with_metadata(project_path, "gpu_test_v01", my_geometry)

print("SUCCESS: Scene and Metadata generated!")