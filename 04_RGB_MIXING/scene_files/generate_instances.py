import argparse
import random

def generate_scene(args):
    directives = []
    
    # --- BRANCH 1: GLOBAL VOLUMES ---
    if args.mode in ["homogeneous", "noise"]:
        if args.mode == "noise":
            directives.append(f'Texture "noise_tex" "float" "pbmperlin" "float scale" [ {args.noise_scale} ]')
            directives.append('MakeNamedMedium "fog_medium" "string type" "heterogeneous"')
            directives.append(f'    "rgb sigma_s" [ {args.sigma_s} ] "float density" "noise_tex"')
        else:
            directives.append('MakeNamedMedium "fog_medium" "string type" "homogeneous"')
            directives.append(f'    "rgb sigma_s" [ {args.sigma_s} ]')
        
        directives.append(f'    "float g" [ {args.g_value} ]')
        directives.append('AttributeBegin')
        directives.append('    MediumInterface "fog_medium" ""')
        directives.append(f'    Shape "sphere" "float radius" [ {args.container_radius} ]')
        directives.append('AttributeEnd')

    # --- BRANCH 2: PARTICLE VOLUMES ---
    elif args.mode in ["grid", "instanced"]:
        directives.append('MakeNamedMedium "parcel_med" "string type" "homogeneous"')
        directives.append(f'    "rgb sigma_s" [ {args.sigma_s} ] "float g" [ {args.g_value} ]')
        directives.append('ObjectBegin "parcel"')
        directives.append('    MediumInterface "parcel_med" ""')
        directives.append(f'    Shape "sphere" "float radius" [ {args.sphere_radius} ]')
        directives.append('ObjectEnd')

        if args.mode == "grid":
            side = int(round(args.num_spheres**(1/3)))
            step = (args.container_radius * 2) / max(1, side)
            for x in range(side):
                for y in range(side):
                    for z in range(side):
                        xp, yp, zp = [-args.container_radius + (i * step) for i in (x, y, z)]
                        if (xp**2 + yp**2 + zp**2) <= args.container_radius**2:
                            directives.append(f'AttributeBegin\n  Translate {xp:.4f} {yp:.4f} {zp:.4f}\n  ObjectInstance "parcel"\nAttributeEnd')
        else:
            for _ in range(args.num_spheres):
                xp, yp, zp = [random.uniform(-args.container_radius, args.container_radius) for _ in range(3)]
                if (xp**2 + yp**2 + zp**2) <= args.container_radius**2:
                    directives.append(f'AttributeBegin\n  Translate {xp:.4f} {yp:.4f} {zp:.4f}\n  ObjectInstance "parcel"\nAttributeEnd')

    return "\n".join(directives)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Updated to match the underscores in the Bash script
    parser.add_argument("--mode", type=str)
    parser.add_argument("--sigma_s", type=str)
    parser.add_argument("--g_value", type=float)
    parser.add_argument("--container_radius", type=float)
    parser.add_argument("--sphere_radius", type=float)
    parser.add_argument("--num_spheres", type=int)
    parser.add_argument("--noise_scale", type=float)
    parser.add_argument("--particles-out", type=str)
    args = parser.parse_args()
    with open(args.particles_out, "w") as f: f.write(generate_scene(args))