#!/bin/bash
set -e

# =============================================================================
# --- 1. CORE CONFIG ---
# =============================================================================
PROJECT_TITLE="04_RGB_MIXING"
RENDER_MODE="homogeneous" 
MASTER_SCENE="04_masterScene.pbrt"
PARTICLES_FILE="particles.pbrt"
PYTHON_SCRIPT="generate_instances.py"
PBRT_BIN="/home/rpf4/pbrt-v4/build/pbrt"

# Path Logic
SCENE_DIR="../scene_files"
ARCHIVE_DIR="../../Archive"

# Ensure Archive directory exists
if [ ! -d "$ARCHIVE_DIR" ]; then mkdir -p "$ARCHIVE_DIR"; fi

# =============================================================================
# --- 2. VOLUMETRIC PARAMETERS ---
# =============================================================================
CONTAINER_RADIUS=15.0
SIGMA_S="0.1 0.1 0.1"  # Macro-scale density for Homogeneous
G_VAL="0.9"

# Dummy values (Required by Python script but ignored in Homogeneous mode)
S_RAD="0" 
NUM="0" 
N_SCALE="0"

# =============================================================================
# --- 3. EXECUTE PIPELINE ---
# =============================================================================

echo "------------------------------------------------"
echo "MODE: $RENDER_MODE | Generating volume..."
echo "------------------------------------------------"

# 1. Run Python generator
python3 "${SCENE_DIR}/${PYTHON_SCRIPT}" \
    --mode "$RENDER_MODE" \
    --sigma_s "$SIGMA_S" \
    --g_value "$G_VAL" \
    --container_radius "$CONTAINER_RADIUS" \
    --sphere_radius "$S_RAD" \
    --num_spheres "$NUM" \
    --noise_scale "$N_SCALE" \
    --particles-out "${SCENE_DIR}/${PARTICLES_FILE}"

# 2. Setup Timestamp and Output Filename
TS=$(date +%Y%m%d_%H%M%S)
FINAL_NAME="${PROJECT_TITLE}_${RENDER_MODE}_${TS}.png"

echo "Starting pbrt-v4 render..."

# 3. Run pbrt-v4 and output directly to Archive
$PBRT_BIN --gpu --stats \
    --outfile "${ARCHIVE_DIR}/${FINAL_NAME}" \
    "${SCENE_DIR}/${MASTER_SCENE}"

echo "------------------------------------------------"
echo "SUCCESS: Saved to ${ARCHIVE_DIR}/${FINAL_NAME}"
echo "------------------------------------------------"