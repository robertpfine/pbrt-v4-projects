#!/usr/bin/env bash

# --- 1. DYNAMIC CONTEXT DISCOVERY ---
PROJECT_ROOT=$(pwd)
ARCHIVE_DIR="$(dirname "$PROJECT_ROOT")/Archive"
CONFIG_FILE="${PROJECT_ROOT}/project_config.json"

# --- 2. VALIDATE CONFIGURATION ---
if [ ! -f "$CONFIG_FILE" ]; then
    echo "----------------------------------------------------------------"
    echo "ERROR: No project_config.json found in current directory:"
    echo "       $PROJECT_ROOT"
    echo "----------------------------------------------------------------"
    exit 1
fi

# --- 3. PARSE CONFIG VIA JQ ---
PROJECT_TITLE=$(jq -r '.project.title' "$CONFIG_FILE")
REMOTE_PATH=$(jq -r '.project.remote_archive_path' "$CONFIG_FILE")
PBRT_BIN=$(jq -r '.runtime.pbrt_binary' "$CONFIG_FILE")
USE_GPU=$(jq -r '.runtime.use_gpu' "$CONFIG_FILE")
SHOW_STATS=$(jq -r '.runtime.show_stats' "$CONFIG_FILE")
SCENE_RELATIVE=$(jq -r '.scene.master_file' "$CONFIG_FILE")

SCENE_PATH="${PROJECT_ROOT}/${SCENE_RELATIVE}"
SCENE_NAME=$(basename "$SCENE_PATH")

if [ ! -f "$SCENE_PATH" ]; then
    echo "ERROR: Target scene file not found at: $SCENE_PATH"
    exit 1
fi

# Validate all volume assets registered in the array
while read -r medium; do
    if [ ! -f "${PROJECT_ROOT}/${medium}" ]; then
        echo "ERROR: Required asset missing: ${PROJECT_ROOT}/${medium}"
        exit 1
    fi
done < <(jq -r '.scene.associated_mediums[]' "$CONFIG_FILE")

# --- 4. BUILD RUNTIME FLAGS ---
CMD_FLAGS=""
if [ "$USE_GPU" = "true" ]; then CMD_FLAGS="$CMD_FLAGS --gpu"; fi
if [ "$SHOW_STATS" = "true" ]; then CMD_FLAGS="$CMD_FLAGS --stats"; fi

TS=$(date +%Y%m%d_%H%M%S)
FINAL_BASE="${ARCHIVE_DIR}/${PROJECT_TITLE}_${TS}"

# --- 5. EXECUTION ---
echo "Executing Pipeline for Project: $PROJECT_TITLE"
cd "${PROJECT_ROOT}" || exit 1

$PBRT_BIN $CMD_FLAGS --outfile "${FINAL_BASE}.png" "$SCENE_PATH"

if [ $? -ne 0 ]; then
    echo "ERROR: pbrt execution failed."
    exit 1
fi

# --- 6. UNIFIED 4-FILE BUNDLE ARCHIVE ---
echo "Archiving complete layout and updating metadata headers..."

# 1. Output PNG image (Created directly by pbrt engine execution above)

# 2. Duplicate and timestamp the master .pbrt scene description file
cp "$SCENE_PATH" "${FINAL_BASE}.pbrt"

# 3. Duplicate and timestamp the project_config.json file
cp "$CONFIG_FILE" "${FINAL_BASE}_config.json"

# 4. Duplicate and timestamp the build_scene.py script if it exists
if [ -f "${PROJECT_ROOT}/build_scene.py" ]; then
    cp "${PROJECT_ROOT}/build_scene.py" "${FINAL_BASE}_build_scene.py"
fi

# Execute safe metadata header injection on the archived pbrt copy
sed "s/^# FILE:.*/# FILE: ${SCENE_NAME}/" "${FINAL_BASE}.pbrt" > "${FINAL_BASE}.tmp" && mv "${FINAL_BASE}.tmp" "${FINAL_BASE}.pbrt"
sed "s/^# PROJECT:.*/# PROJECT: ${PROJECT_TITLE}/" "${FINAL_BASE}.pbrt" > "${FINAL_BASE}.tmp" && mv "${FINAL_BASE}.tmp" "${FINAL_BASE}.pbrt"

# Sync full bundle to Cloud
echo "Syncing 4-file archive bundle to Google Drive..."
rclone copy "$ARCHIVE_DIR" "$REMOTE_PATH"

echo "------------------------------------------------"
echo "Success: Render Pipeline Complete."
echo "------------------------------------------------"
