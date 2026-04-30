// make_nvdb.cpp
//
// Reads a raw density binary produced by gen_density.py and writes a
// NanoVDB .nvdb file suitable for use with pbrt-v4's "nanovdb" medium.
//
// Compile:
//   g++ -std=c++17 \
//       -I/home/rpf4/pbrt-v4/src/ext/openvdb/nanovdb \
//       -O2 -o make_nvdb make_nvdb.cpp
//
// Usage:
//   ./make_nvdb density.bin density.nvdb
//
// The resulting density.nvdb can be referenced in a pbrt scene as:
//   MakeNamedMedium "vol"
//       "string type"    [ "nanovdb" ]
//       "string filename" [ "density.nvdb" ]
//       "rgb sigma_s"    [ 1.0 1.0 1.0 ]
//       "rgb sigma_a"    [ 0.05 0.05 0.05 ]

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

// NanoVDB — single header, no external dependencies
#define NANOVDB_USE_IOSTREAMS
#include <nanovdb/NanoVDB.h>
#include <nanovdb/util/GridBuilder.h>
#include <nanovdb/util/IO.h>

int main(int argc, char* argv[])
{
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <density.bin> <output.nvdb>\n", argv[0]);
        return 1;
    }

    const char* bin_path  = argv[1];
    const char* nvdb_path = argv[2];

    // -----------------------------------------------------------------------
    // Read raw binary
    // -----------------------------------------------------------------------
    FILE* f = fopen(bin_path, "rb");
    if (!f) {
        fprintf(stderr, "Cannot open %s\n", bin_path);
        return 1;
    }

    int32_t nx, ny, nz;
    fread(&nx, sizeof(int32_t), 1, f);
    fread(&ny, sizeof(int32_t), 1, f);
    fread(&nz, sizeof(int32_t), 1, f);

    const int total = nx * ny * nz;
    std::vector<float> density(total);
    fread(density.data(), sizeof(float), total, f);
    fclose(f);

    printf("Read %dx%dx%d grid (%d voxels) from %s\n", nx, ny, nz, total, bin_path);

    // -----------------------------------------------------------------------
    // Build NanoVDB FloatGrid named "density"
    // pbrt-v4 looks for a grid named "density" inside the .nvdb file.
    // -----------------------------------------------------------------------
    auto builder = nanovdb::GridBuilder<float>(0.0f);  // background = 0
    auto acc = builder.getAccessor();

    for (int k = 0; k < nz; ++k) {
        for (int j = 0; j < ny; ++j) {
            for (int i = 0; i < nx; ++i) {
                float val = density[k * ny * nx + j * nx + i];
                if (val > 0.0f)   // skip background voxels — keeps file sparse
                    acc.setValue(nanovdb::Coord(i, j, k), val);
            }
        }
    }

    // World-space transform: map voxel indices to [-1, 1] on each axis,
    // matching the default p0/p1 bounds used in the pbrt scene.
    const double voxel_size_x = 3.0 / nx;
    const double voxel_size_y = 3.0 / ny;
    const double voxel_size_z = 3.0 / nz;
    // Use the smallest voxel size for a uniform scale (grid may be non-cubic)
    const double voxel_size = std::min({voxel_size_x, voxel_size_y, voxel_size_z});
    const nanovdb::Vec3d origin(-1.5, -1.5, -1.5);

    auto handle = builder.getHandle<>(
        voxel_size,   // uniform voxel size
        origin,       // world-space origin of voxel (0,0,0)
        "density"     // grid name — pbrt looks for this
    );

    // -----------------------------------------------------------------------
    // Write .nvdb
    // -----------------------------------------------------------------------
    nanovdb::io::writeGrid(nvdb_path, handle);
    printf("Written: %s\n", nvdb_path);

    return 0;
}
