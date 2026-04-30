#!/bin/bash

# --- 1. CONFIGURATION ---
PROJECT_TITLE="04_RGB_MIXING-POINTILLISM"
SCENE_NAME="pointillist_MASTER.pbrt"
REMOTE_PATH="gdrive:wipImages/pbrt-v4"
PBRT_BIN="/home/rpf4/pbrt-v4/build/pbrt"

# --- 2. AUTOMATED PATH LOGIC ---
SCRIPT_PATH=$(readlink -f "$0")
BASH_DIR=$(dirname "$SCRIPT_PATH")
PROJECT_DIR=$(dirname "$BASH_DIR")
ARCHIVE_DIR="$(dirname "$PROJECT_DIR")/Archive"
SCENE_DIR="${PROJECT_DIR}/scene_files"

# --- 3. DIRECT FILE CHECK ---
SCENE_PATH="${SCENE_DIR}/${SCENE_NAME}"

if [ ! -f "$SCENE_PATH" ]; then
    echo "------------------------------------------------"
    echo "ERROR: File not found: $SCENE_PATH"
    echo "------------------------------------------------"
    exit 1
fi

# --- 4. EXECUTION ---
TS=$(date +%Y%m%d_%H%M%S)
FINAL_BASE="${ARCHIVE_DIR}/${PROJECT_TITLE}_${TS}"

echo "Starting GPU Render for: $SCENE_NAME..."
$PBRT_BIN --gpu --stats --outfile "${FINAL_BASE}.png" "$SCENE_PATH"
#$PBRT_BIN --nthreads 24 --stats --outfile "${FINAL_BASE}.png" "$SCENE_PATH"

# Archive code and image together
cp "$SCENE_PATH" "${FINAL_BASE}.pbrt"

# Sync to Cloud
echo "Syncing Archive to Google Drive..."
rclone copy "$ARCHIVE_DIR" "$REMOTE_PATH"

echo "------------------------------------------------"
echo "Success: Rendered and Archived to ${FINAL_BASE}.png"
echo "------------------------------------------------"