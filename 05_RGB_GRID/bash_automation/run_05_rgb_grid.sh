#!/bin/bash
set -e

# --- 1. CONFIGURATION ---
PROJECT_TITLE="05_RGB_GRID"
REMOTE_PATH="gdrive:wipImages/pbrt-v4"
PBRT_BIN="/home/rpf4/pbrt-v4/build/pbrt"

# --- 2. AUTOMATED PATH LOGIC ---
SCRIPT_PATH=$(readlink -f "$0")
BASH_DIR=$(dirname "$SCRIPT_PATH")
PROJECT_DIR=$(dirname "$BASH_DIR")
ARCHIVE_DIR="$(dirname "$PROJECT_DIR")/Archive"

GENERATED_DIR="${PROJECT_DIR}/generated"
SCENE_PATH="${GENERATED_DIR}/master_scene.pbrt"

# --- 3. BUILD STEP ---
echo "------------------------------------------------"
echo "Building scene via Python..."
echo "------------------------------------------------"

cd "$PROJECT_DIR"
python3 build_scene.py

# --- 4. VERIFY SCENE EXISTS ---
if [ ! -f "$SCENE_PATH" ]; then
    echo "------------------------------------------------"
    echo "ERROR: Scene not generated: $SCENE_PATH"
    echo "------------------------------------------------"
    exit 1
fi

# --- 5. EXECUTION ---
TS=$(date +%Y%m%d_%H%M%S)
FINAL_BASE="${ARCHIVE_DIR}/${PROJECT_TITLE}_${TS}"

echo "------------------------------------------------"
echo "Starting GPU Render..."
echo "------------------------------------------------"

$PBRT_BIN --gpu --stats --outfile "${FINAL_BASE}.png" "$SCENE_PATH"

# --- 6. ARCHIVE FILES ---
cp "$SCENE_PATH" "${FINAL_BASE}.pbrt"
cp "${PROJECT_DIR}/config.json" "${FINAL_BASE}_config.json"
cp "${PROJECT_DIR}/build_scene.py" "${FINAL_BASE}_build_scene.py"

# --- 7. SYNC TO CLOUD ---
echo "Syncing Archive to Google Drive..."
rclone copy "$ARCHIVE_DIR" "$REMOTE_PATH"

echo "------------------------------------------------"
echo "Success: Rendered and Archived to ${FINAL_BASE}.png"
echo "------------------------------------------------"
