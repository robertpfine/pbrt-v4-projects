# HotCoffee System Recovery & PBRT-v4 Setup Guide

This guide outlines the exact dependencies and environment configurations required to rebuild the PBRT-v4 rendering engine on a fresh native Ubuntu installation targeting the **RTX 5090 (Blackwell)** hardware pipeline.

## 1. Core System & Compilers
Before configuring PBRT, the system requires essential build utilities and a compatible host compiler matrix (GCC/G++).

```bash
# Update package repositories
sudo apt update

# Install essential build tools, CMake, and image libraries
sudo apt install -y build-essential cmake git libx11-dev libxrandr-dev \
libxinerama-dev libxcursor-dev libxi-dev libgl1-mesa-dev \
libopenexr-dev openexr zlib1g-dev

# Install matching GCC/G++ 12 compilers to ensure CUDA compatibility
sudo apt install -y gcc-12 g++-12
2. NVIDIA Driver & CUDA Toolkit Installation
The RTX 5090 requires modern driver architectures and a CUDA toolkit version capable of identifying the Blackwell framework.

Install the NVIDIA Production Driver (Version 595.58 or newer) via the Ubuntu Software & Updates "Additional Drivers" panel or directly from the NVIDIA website.

Download and install the CUDA Toolkit (Version 12.x) ensuring that the nvcc compiler is bound to the system paths.

Essential Environment Variables
To prevent CMake from running "blind" to your hardware tooling, append the following paths to the bottom of your ~/.bashrc file:

Bash
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
export CUDA_HOME=/usr/local/cuda
Run source ~/.bashrc to update your current terminal session immediately after saving.

3. OptiX SDK Placement
PBRT-v4 relies on the NVIDIA OptiX Ray Tracing Engine for hardware-accelerated intersection traversal. Because OptiX is a proprietary SDK, it must be downloaded manually.

Download the OptiX SDK (Version 8.0 or newer) from the NVIDIA Developer Zone.

Extract the contents and place the directory safely inside your home path: ~/NVIDIA-OptiX-SDK/

Export the path variable to your system environment:

Bash
export OPTIX_LOOKUP_DIR=~/NVIDIA-OptiX-SDK
4. Repository Retrieval & Clean Native Compilation
With the system environment fully pathed and confirmed, clone the codebase directly from your repository and pass the strict target architecture profile.

Bash
# Clone the repository and fetch internal submodules
cd ~
git clone --recursive <your-github-repo-link-here>
cd pbrt-v4

# Wipe any corrupt configurations and build fresh targeting Blackwell sm_120
rm -rf build/
CC=gcc-12 CXX=g++-12 cmake -B build -DCMAKE_BUILD_TYPE=Release -DPBRT_GPU_SHADER_MODEL=sm_120

# Execute compilation using all available CPU processing cores
cmake --build build --config Release -j$(nproc)
5. Automation Verification
Once compilation concludes, verify the executable location and run your project automation to ensure the path-tracing kernels load seamlessly onto the GPU.

Bash
# Verify binaries exist
ls build/bin/

# Step into your project directory and execute a test render
cd ~/my-pbrt-projects/05_RGB_GRID
bash bash_automation/run_05_rgb_grid.sh
