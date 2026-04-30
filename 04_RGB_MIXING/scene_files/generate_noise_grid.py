import numpy as np

def generate_pbrt_grid(res=64, filename="noise_grid.pbrt"):
    print(f"Calculating {res}^3 noise grid...")
    
    # 1. Define the coordinate space (0 to 10)
    coords = np.linspace(0, 10, res)
    x, y, z = np.meshgrid(coords, coords, coords, indexing='ij')
    
    # 2. Generate procedural noise pattern
    # This uses overlapping sine waves to simulate Perlin-like 'clouds'
    noise = (np.sin(x * 0.8) * np.cos(y * 0.8) + np.sin(z * 1.2)) * 0.5 + 0.5
    
    # Apply a threshold to create voids (0 = no fog, 1 = max density)
    noise = np.where(noise > 0.5, (noise - 0.5) * 2.0, 0)
    noise = np.clip(noise, 0, 1)
    
    # 3. Flatten the 3D array into a single space-separated string
    flat_noise = noise.flatten()
    noise_string = " ".join([f"{v:.4f}" for v in flat_noise])

    # 4. Write the PBRT file
    with open(filename, "w") as f:
        f.write('MakeNamedMedium "perlin_grid_medium"\n')
        f.write('    "string type" [ "uniformgrid" ]\n')
        f.write(f'    "integer nx" [{res}] "integer ny" [{res}] "integer nz" [{res}]\n')
        # p0 and p1 define the physical corners of the volume in World Space
        f.write('    "point3 p0" [ -10 -10 -10 ] "point3 p1" [ 10 10 10 ]\n')
        f.write(f'    "float density" [ {noise_string} ]\n')
        f.write('    "rgb sigma_s" [ 20 20 20 ]\n')
        f.write('    "rgb sigma_a" [ 0 0 0 ]\n')

    print(f"Success: Wrote grid data to {filename}")

if __name__ == "__main__":
    generate_pbrt_grid(res=64) # Start with 64 for speed; increase to 128 for detail