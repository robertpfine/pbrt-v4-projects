#!/bin/bash
############################################################
# PROJECT: 04_RGB_MIXING
# FILE: render_rgbgrid_poc.sh
# VERSION: rgbgrid proof of concept
############################################################

# --- PATHS ---
SCRIPT_PATH=$(readlink -f "$0")
BASH_DIR=$(dirname "$SCRIPT_PATH")
PROJECT_DIR=$(dirname "$BASH_DIR")
ARCHIVE_DIR="$(dirname "$PROJECT_DIR")/Archive"
SCENE_DIR="${PROJECT_DIR}/scene_files"
PBRT_BIN="/home/rpf4/pbrt-v4/build/pbrt"
PROJECT_TITLE="04_RGB_MIXING"

SCENE_FILE="${SCENE_DIR}/rgbgrid_poc_YYYYYY.pbrt"
MEDIUM_FILE="${SCENE_DIR}/rgbgrid_medium_YYYYYY.pbrt"

# --- GENERATE MEDIUM ---
echo "Generating rgbgrid medium..."
python3 "${SCENE_DIR}/gen_rgbgrid_poc_YYYYYY (2).py"
mv rgbgrid_medium_YYYYYY.pbrt "$MEDIUM_FILE"

# --- RENDER ---
TS=$(date +%Y%m%d_%H%M%S)
FINAL_BASE="${ARCHIVE_DIR}/${PROJECT_TITLE}_${TS}"

echo "Rendering..."
"$PBRT_BIN" --gpu --stats --outfile "${FINAL_BASE}.png" "$SCENE_FILE"

# --- ARCHIVE ---
echo "Archiving..."
cp "$SCENE_FILE"  "${FINAL_BASE}.pbrt"
cp "${SCENE_DIR}/gen_rgbgrid_poc_YYYYYY (2).py" "${FINAL_BASE}_GRID.py"
#cp "$MEDIUM_FILE" "${FINAL_BASE}_MEDIUM.pbrt"

# --- SYNC ---
echo "Syncing to Google Drive..."
rclone copy "$ARCHIVE_DIR" "gdrive:wipImages/pbrt-v4"

echo "------------------------------------------------"
echo "Success: ${FINAL_BASE}.png"
echo "------------------------------------------------"
