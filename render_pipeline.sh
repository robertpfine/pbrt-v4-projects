#!/usr/bin/env bash
# =============================================================================
# render_pipeline.sh  —  pbrt-v4 project render pipeline
# Usage: ./render_pipeline.sh <project-name>
# Example: ./render_pipeline.sh rgbgrid-medium
# =============================================================================

# --- 1. ARGUMENT VALIDATION ---
if [ -z "$1" ]; then
    echo "ERROR: No project name supplied."
    echo "Usage: ./render_pipeline.sh <project-name>"
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="$1"
PROJECT_ROOT="${REPO_ROOT}/${PROJECT_NAME}"
CONFIG_FILE="${PROJECT_ROOT}/config.json"
ARCHIVE_DIR="${REPO_ROOT}/Archive"

# --- 2. VALIDATE PROJECT DIRECTORY AND CONFIG ---
if [ ! -d "$PROJECT_ROOT" ]; then
    echo "ERROR: Project directory not found: $PROJECT_ROOT"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: config.json not found in: $PROJECT_ROOT"
    exit 1
fi

# --- 3. PARSE CONFIG VIA JQ ---
CONFIG_NAME=$(jq -r '.project.name'                "$CONFIG_FILE")
REMOTE_PATH=$(jq -r '.project.remote_archive_path' "$CONFIG_FILE")
PBRT_BIN=$(jq    -r '.runtime.pbrt_binary'         "$CONFIG_FILE")
USE_GPU=$(jq     -r '.runtime.use_gpu'             "$CONFIG_FILE")
SHOW_STATS=$(jq  -r '.runtime.show_stats'          "$CONFIG_FILE")
RUN_BUILD=$(jq   -r '.pipeline.build_scene.enabled' "$CONFIG_FILE")
RUN_SYNC=$(jq    -r '.pipeline.rclone_sync.enabled' "$CONFIG_FILE")
SCENE_RELATIVE=$(jq -r '.scene.master_file'        "$CONFIG_FILE")
SCENE_PATH="${PROJECT_ROOT}/${SCENE_RELATIVE}"

# --- 4. VALIDATE PROJECT NAME MATCHES CONFIG ---
if [ "$CONFIG_NAME" != "$PROJECT_NAME" ]; then
    echo "ERROR: Argument '$PROJECT_NAME' does not match project.name '$CONFIG_NAME' in config."
    exit 1
fi

# --- 5. RUN BUILD SCRIPT (if enabled) ---
if [ "$RUN_BUILD" = "true" ]; then
    BUILD_SCRIPT="${PROJECT_ROOT}/build_scene.py"
    if [ ! -f "$BUILD_SCRIPT" ]; then
        echo "ERROR: build_scene.py not found in: $PROJECT_ROOT"
        exit 1
    fi
    echo "Running build_scene.py for project: $PROJECT_NAME"
    python3 "$BUILD_SCRIPT" "$CONFIG_FILE"
    if [ $? -ne 0 ]; then
        echo "ERROR: build_scene.py failed."
        exit 1
    fi
else
    echo "Skipping build_scene.py (disabled in config)."
fi

# --- 5b. RUN SPACE COLONIZATION (if enabled) ---
TREE_ENABLED=$(jq -r '.scene.tree.enabled // false' "$CONFIG_FILE")
if [ "$TREE_ENABLED" = "true" ]; then
    SPACE_COL="${REPO_ROOT}/space_col.py"
    if [ ! -f "$SPACE_COL" ]; then
        echo "ERROR: space_col.py not found in repo root."
        exit 1
    fi
    echo "Running space_col.py for project: $PROJECT_NAME"
    python3 "$SPACE_COL" "$CONFIG_FILE"
    if [ $? -ne 0 ]; then
        echo "ERROR: space_col.py failed."
        exit 1
    fi
else
    echo "Skipping space_col.py (tree disabled in config)."
fi

# --- 6. VALIDATE SCENE FILE EXISTS ---
if [ ! -f "$SCENE_PATH" ]; then
    echo "ERROR: Scene file not found at: $SCENE_PATH"
    exit 1
fi

# --- 7. BUILD PBRT RUNTIME FLAGS ---
CMD_FLAGS=""
if [ "$USE_GPU"    = "true" ]; then CMD_FLAGS="$CMD_FLAGS --gpu";   fi
if [ "$SHOW_STATS" = "true" ]; then CMD_FLAGS="$CMD_FLAGS --stats"; fi

TS=$(date +%Y%m%d_%H%M%S)
mkdir -p "$ARCHIVE_DIR"
FINAL_BASE="${ARCHIVE_DIR}/${PROJECT_NAME}_${TS}"

# --- 8. RUN PBRT ---
echo "----------------------------------------------------------------"
echo "Rendering: $PROJECT_NAME"
echo "Scene:     $SCENE_PATH"
echo "Output:    ${FINAL_BASE}.png"
echo "----------------------------------------------------------------"
cd "${PROJECT_ROOT}" || exit 1

$PBRT_BIN $CMD_FLAGS --outfile "${FINAL_BASE}.png" "$SCENE_PATH"

if [ $? -ne 0 ]; then
    echo "ERROR: pbrt execution failed."
    exit 1
fi

# --- 9. ARCHIVE 4-FILE BUNDLE ---
echo "Archiving project files..."
cp "$SCENE_PATH"                    "${FINAL_BASE}.pbrt"
cp "$CONFIG_FILE"                   "${FINAL_BASE}_config.json"
cp "${PROJECT_ROOT}/build_scene.py" "${FINAL_BASE}_build_scene.py" 2>/dev/null || true
cp "${REPO_ROOT}/render_pipeline.sh" "${FINAL_BASE}_render_pipeline.sh" 2>/dev/null || true

# Update metadata headers in archived .pbrt copy
sed -i "s|^# FILE:.*|# FILE: scene.pbrt|"          "${FINAL_BASE}.pbrt"
sed -i "s|^# PROJECT:.*|# PROJECT: $PROJECT_NAME|" "${FINAL_BASE}.pbrt"

# --- 10. RCLONE SYNC (if enabled) ---
if [ "$RUN_SYNC" = "true" ]; then
    echo "Syncing archive bundle to Google Drive..."
    rclone copy "$ARCHIVE_DIR" "$REMOTE_PATH" \
        --include "${PROJECT_NAME}_${TS}.png" \
        --include "${PROJECT_NAME}_${TS}.pbrt" \
        --include "${PROJECT_NAME}_${TS}_config.json" \
        --include "${PROJECT_NAME}_${TS}_build_scene.py" \
        --include "${PROJECT_NAME}_${TS}_render_pipeline.sh" \
        --drive-chunk-size=64M \
        --low-level-retries=5

    if [ $? -eq 0 ]; then
        echo "Google Drive sync complete."
    else
        echo "WARNING: Render succeeded locally, but Google Drive sync failed."
        echo "         Files are preserved in: $ARCHIVE_DIR"
    fi
else
    echo "Skipping rclone sync (disabled in config)."
fi

echo "----------------------------------------------------------------"
echo "Pipeline complete: $PROJECT_NAME"
echo "----------------------------------------------------------------"
