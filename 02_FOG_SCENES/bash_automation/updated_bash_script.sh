#!/bin/bash

# 1. Dynamic Path Detection
# Calculates paths relative to the script's location in bash_automation/
SCRIPT_PATH=$(readlink -f "$0")
BASH_DIR=$(dirname "$SCRIPT_PATH")
PROJECT_DIR=$(dirname "$BASH_DIR")
PROJECT_NAME=$(basename "$PROJECT_DIR")

# 2. Global Archive and Timestamp
# Targets the root 'Archive' directory and generates a unique ID
ARCHIVE_DIR="$(dirname "$PROJECT_DIR")/Archive"
TS=$(date +%Y%m%d_%H%M%S)

# 3. Define the Archive Pair Base Name (Project Name && Timestamp)
FINAL_BASE="${ARCHIVE_DIR}/${PROJECT_NAME}_${TS}"

# 4. Reference the Scene
# We point to the new scene_files location established in your recent move
SCENE_PATH="${PROJECT_DIR}/scene_files/gold_standard-v4.pbrt"

# 5. Run PBRT-v4 GPU Render
# Bypasses any internal filenames to ensure the Archive pair is perfectly matched
/home/rpf4/pbrt-v4/build/pbrt --gpu --stats --outfile "${FINAL_BASE}.png" "$SCENE_PATH"

# 6. Create the Archive Pair
# Copies the exact code used for the render side-by-side with the image
cp "$SCENE_PATH" "${FINAL_BASE}.pbrt"

echo "------------------------------------------------"
echo "Project: ${PROJECT_NAME}"
echo "Rendered and Archived to: ${FINAL_BASE}.png"
echo "Code Archived to: ${FINAL_BASE}.pbrt"
echo "------------------------------------------------"