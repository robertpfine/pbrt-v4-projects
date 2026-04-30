#!/bin/bash

# Dynamic Path Detection
SCRIPT_PATH=$(readlink -f "$0")
BASH_DIR=$(dirname "$SCRIPT_PATH")
PROJECT_DIR=$(dirname "$BASH_DIR")
PROJECT_NAME=$(basename "$PROJECT_DIR")

# Global Archive and Timestamp
ARCHIVE_DIR="$(dirname "$PROJECT_DIR")/Archive"
TS=$(date +%Y%m%d_%H%M%S)
FINAL_BASE="${ARCHIVE_DIR}/${PROJECT_NAME}_${TS}"

# CONFIGURATION: Update this to point to your specific .pbrt file
SCENE_PATH="${PROJECT_DIR}/scene_files/YOUR_SCENE_HERE.pbrt"

# Run PBRT-v4 GPU Render
/home/rpf4/pbrt-v4/build/pbrt --gpu --stats --outfile "${FINAL_BASE}.png" "$SCENE_PATH"

# Create the Archive Pair
cp "$SCENE_PATH" "${FINAL_BASE}.pbrt"

echo "------------------------------------------------"
echo "Project: ${PROJECT_NAME}"
echo "Archived to: ${FINAL_BASE}.png/.pbrt"
echo "------------------------------------------------"
