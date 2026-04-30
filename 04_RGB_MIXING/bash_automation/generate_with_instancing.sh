#!/bin/bash

# =============================================================================
# render_archive.sh
# PROJECT: RGB POINTILLISM
# 
# Automated pipeline:
#   1. Generate particle field (Python)
#   2. Render scene (pbrt GPU)
#   3. Archive all files together
#   4. Sync to Google Drive
#
# Usage:
#   ./render_archive.sh
# =============================================================================

# --- 1. CONFIGURATION ---
PROJECT_TITLE="04_RGB_MIXING"
MASTER_SCENE="pointillist_v2_master.pbrt"
PARTICLES_FILE="particles.pbrt"
PYTHON_SCRIPT="generate_instances.py"
REMOTE_PATH="gdrive:wipImages/pbrt-v4"
PBRT_BIN="/home/rpf4/pbrt-v4/build/pbrt"

# --- 2. PARTICLE PARAMETERS ---
# These are passed directly to generate_instances.py
# Change these to experiment — no need to touch the Python script
NUM_SPHERES=50000
SPHERE_RADIUS=0.05
LIGHT_INTENSITY=100000
REFLECTANCE=0.9
SEED=42

# --- 3. AUTOMATED PATH LOGIC ---
SCRIPT_PATH=$(readlink -f "$0")
BASH_DIR=$(dirname "$SCRIPT_PATH")
PROJECT_DIR=$(dirname "$BASH_DIR")
ARCHIVE_DIR="$(dirname "$PROJECT_DIR")/Archive"
SCENE_DIR="${PROJECT_DIR}/scene_files"

echo "================================================"
echo "  PROJECT : $PROJECT_TITLE"
echo "  SCENE   : $MASTER_SCENE"
echo "  SPHERES : $NUM_SPHERES"
echo "  RADIUS  : $SPHERE_RADIUS"
echo "  LIGHTS  : $LIGHT_INTENSITY"
echo "================================================"

# --- 4. CHECK DEPENDENCIES ---
if [ ! -f "${SCENE_DIR}/${PYTHON_SCRIPT}" ]; then
    echo "ERROR: Python script not found: ${SCENE_DIR}/${PYTHON_SCRIPT}"
    exit 1
fi

if [ ! -f "$PBRT_BIN" ]; then
    echo "ERROR: pbrt binary not found: $PBRT_BIN"
    exit 1
fi

if [ ! -d "$ARCHIVE_DIR" ]; then
    echo "Creating archive directory: $ARCHIVE_DIR"
    mkdir -p "$ARCHIVE_DIR"
fi

# --- 5. GENERATE PARTICLE FIELD ---
echo ""
echo "Step 1/4: Generating particle field..."
echo "  Spheres : $NUM_SPHERES"
echo "  Radius  : $SPHERE_RADIUS"

python3 "${SCENE_DIR}/${PYTHON_SCRIPT}" \
    --num-spheres      $NUM_SPHERES \
    --sphere-radius    $SPHERE_RADIUS \
    --light-intensity  $LIGHT_INTENSITY \
    --reflectance      $REFLECTANCE \
    --seed             $SEED \
    --master-out       "${SCENE_DIR}/${MASTER_SCENE}" \
    --particles-out    "${SCENE_DIR}/${PARTICLES_FILE}"

if [ $? -ne 0 ]; then
    echo "------------------------------------------------"
    echo "ERROR: Particle generation failed."
    echo "------------------------------------------------"
    exit 1
fi

echo "  Done."

# --- 6. VERIFY FILES EXIST ---
echo ""
echo "Step 2/4: Verifying files..."

if [ ! -f "${SCENE_DIR}/${MASTER_SCENE}" ]; then
    echo "ERROR: Master scene not found: ${SCENE_DIR}/${MASTER_SCENE}"
    exit 1
fi

if [ ! -f "${SCENE_DIR}/${PARTICLES_FILE}" ]; then
    echo "ERROR: Particles file not found: ${SCENE_DIR}/${PARTICLES_FILE}"
    exit 1
fi

echo "  Master scene : ${SCENE_DIR}/${MASTER_SCENE}"
echo "  Particles    : ${SCENE_DIR}/${PARTICLES_FILE}"
echo "  Done."

# --- 7. RENDER ---
echo ""
echo "Step 3/4: Rendering..."

TS=$(date +%Y%m%d_%H%M%S)
FINAL_BASE="${ARCHIVE_DIR}/${PROJECT_TITLE}_${TS}"

$PBRT_BIN --gpu --stats \
    --outfile "${FINAL_BASE}.png" \
    "${SCENE_DIR}/${MASTER_SCENE}"

if [ $? -ne 0 ]; then
    echo "------------------------------------------------"
    echo "ERROR: Render failed."
    echo "------------------------------------------------"
    exit 1
fi

echo "  Output: ${FINAL_BASE}.png"
echo "  Done."

# --- 8. ARCHIVE ---
echo ""
echo "Step 4/4: Archiving..."

# Archive master scene, particles, and the Python script that generated them
# so every render is fully reproducible
cp "${SCENE_DIR}/${MASTER_SCENE}"   "${FINAL_BASE}_master.pbrt"
cp "${SCENE_DIR}/${PARTICLES_FILE}" "${FINAL_BASE}_particles.pbrt"
cp "${SCENE_DIR}/${PYTHON_SCRIPT}"  "${FINAL_BASE}_generate.py"

# Write a parameters log alongside the render
cat > "${FINAL_BASE}_params.txt" << EOF
Render Parameters
=================
Date           : $(date)
Project        : $PROJECT_TITLE
Master scene   : $MASTER_SCENE
Num spheres    : $NUM_SPHERES
Sphere radius  : $SPHERE_RADIUS
Light intensity: $LIGHT_INTENSITY
Reflectance    : $REFLECTANCE
Seed           : $SEED
EOF

echo "  Archived to: $FINAL_BASE"
echo "  Done."

# --- 9. SYNC TO CLOUD ---
echo ""
echo "Syncing to Google Drive..."
rclone copy "$ARCHIVE_DIR" "$REMOTE_PATH"

echo ""
echo "================================================"
echo "  SUCCESS"
echo "  Render : ${FINAL_BASE}.png"
echo "================================================"
