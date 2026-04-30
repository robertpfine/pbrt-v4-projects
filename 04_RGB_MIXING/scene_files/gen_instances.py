import sys
import random

def generate_pbrt_particle_cloud(num_mediums, particle_radius, container_radius):
    directives = []
    directives.append('MakeNamedMedium "particle_haze" "string type" "homogeneous"')
    directives.append('    "rgb sigma_s" [ 15 15 15 ] "rgb sigma_a" [ 0.01 0.01 0.01 ]')
    directives.append('    "float g" [ 0.9 ]\n')

    directives.append('ObjectBegin "medium_sphere_holder"')
    directives.append('    MediumInterface "particle_haze" ""')
    directives.append(f'    Shape "sphere" "float radius" [ {particle_radius} ]')
    directives.append('ObjectEnd\n')

    count = 0
    while count < num_mediums:
        x = random.uniform(-container_radius, container_radius)
        y = random.uniform(-container_radius, container_radius)
        z = random.uniform(-container_radius, container_radius)
        if (x**2 + y**2 + z**2) <= container_radius**2:
            directives.append('AttributeBegin')
            directives.append(f'    Translate {x:.4f} {y:.4f} {z:.4f}')
            directives.append('    ObjectInstance "medium_sphere_holder"')
            directives.append('AttributeEnd')
            count += 1
    return "\n".join(directives)

if __name__ == "__main__":
    # Pulling arguments from Bash: python generate_fog.py [count] [p_rad] [c_rad]
    n = int(sys.argv[1])
    p_rad = float(sys.argv[2])
    c_rad = float(sys.argv[3])
    
    print(generate_pbrt_particle_cloud(n, p_rad, c_rad))