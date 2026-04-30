#!/bin/bash

# 1. Path Configuration
# Determines project name automatically from the parent folder of the script's location
PROJECT_NAME=$(basename "$(dirname "$(dirname "$(readlink -f "$0")")")")
HISTORY_DIR="/home/rpf4/my-pbrt-projects/History-Archive"
SCENE_PATH="/home/rpf4/my-pbrt-projects/${PROJECT_NAME}/scene_files/fog_20260209_222133.pbrt"
TS=$(date +%Y%m%d_%H%M%S)

# 2. Define the Pair Naming Convention (Project Name && Timestamp)
FINAL_BASE="${HISTORY_DIR}/${PROJECT_NAME}_${TS}"

# 3. Execution (GPU path)
/home/rpf4/pbrt-v4/build/pbrt --gpu --stats --outfile "${FINAL_BASE}.png" "$SCENE_PATH"

# 4. Create the Pair
cp "$SCENE_PATH" "${FINAL_BASE}.pbrt"

# 5. Mirror to Cloud
rclone copy "$HISTORY_DIR" "gdrive:pbrt_history"