#!/bin/bash

# Path logic: finds the root Archive relative to this project
SCRIPT_PATH=$(readlink -f "$0")
BASH_DIR=$(dirname "$SCRIPT_PATH")
PROJECT_DIR=$(dirname "$BASH_DIR")
PROJECT_NAME=$(basename "$PROJECT_DIR")
ARCHIVE_DIR="$(dirname "$PROJECT_DIR")/Archive"

TS=$(date +%Y%m%d_%H%M%S)
FINAL_BASE="${ARCHIVE_DIR}/${PROJECT_NAME}_${TS}"

# CONFIGURATION: Update this filename when you create your .pbrt template
SCENE_PATH="${PROJECT_DIR}/scene_files/gold_standard-v4.pbrt"

# Run PBRT-v4 GPU Render
/home/rpf4/pbrt-v4/build/pbrt --gpu --stats --outfile "${FINAL_BASE}.png" "$SCENE_PATH"

# Archive the code as a pair with the image
cp "$SCENE_PATH" "${FINAL_BASE}.pbrt"

# Mirror the Global Archive to your specific Google Drive folder
rclone copy "$ARCHIVE_DIR" "gdrive:wipImages/pbrt-v4"

echo "------------------------------------------------"
echo "Rendered and Archived to: ${FINAL_BASE}.png"
echo "Cloud Synced to: wipImages/pbrt-v4"
echo "------------------------------------------------"
