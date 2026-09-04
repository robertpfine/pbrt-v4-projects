#!/usr/bin/env bash
# =============================================================================
# render_pipeline.sh  —  PBRT-v4 Art Studio render pipeline
# Usage: ./render_pipeline.sh [path/to/config.json]
# With no argument, renders scene_workspace/config.json.
# =============================================================================

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_INPUT="${1:-${REPO_ROOT}/scene_workspace/config.json}"
if [ -d "$CONFIG_INPUT" ]; then
    CONFIG_INPUT="${CONFIG_INPUT}/config.json"
fi
ARCHIVE_DIR="${REPO_ROOT}/Archive"

# --- 1. RESOLVE AND FREEZE THE WORKING SCENE ---
if [ ! -f "$CONFIG_INPUT" ]; then
    echo "ERROR: Scene configuration not found: $CONFIG_INPUT"
    exit 1
fi
SOURCE_CONFIG_FILE="$(realpath "$CONFIG_INPUT")"
TS=$(date +%Y%m%d_%H%M%S)
SNAPSHOT_INFO=$(python3 "${REPO_ROOT}/render_snapshot.py" create \
    --repository-root "$REPO_ROOT" \
    --config "$SOURCE_CONFIG_FILE" \
    --timestamp "$TS")
if [ $? -ne 0 ]; then
    echo "ERROR: Could not create immutable render-input snapshot."
    exit 1
fi
CONFIG_FILE=$(printf '%s' "$SNAPSHOT_INFO" | jq -r '.config')
SCENE_ROOT=$(printf '%s' "$SNAPSHOT_INFO" | jq -r '.scene_root')
SNAPSHOT_REPO_ROOT=$(printf '%s' "$SNAPSHOT_INFO" | jq -r '.repository_root')
RUN_DIRECTORY=$(printf '%s' "$SNAPSHOT_INFO" | jq -r '.run_directory')
echo "Render inputs frozen: $RUN_DIRECTORY"

# --- 2. PARSE CONFIG VIA JQ ---
SCENE_NAME=$(jq -r '.scene.name // "untitled_scene"' "$CONFIG_FILE")
ARCHIVE_STEM=$(printf '%s' "$SNAPSHOT_INFO" | jq -r '.archive_stem')
REMOTE_PATH=$(jq -r '.archive.remote_path'          "$CONFIG_FILE")
PBRT_BIN=$(jq    -r '.runtime.pbrt_binary'         "$CONFIG_FILE")
USE_GPU=$(jq     -r '.runtime.use_gpu'             "$CONFIG_FILE")
SHOW_STATS=$(jq  -r '.runtime.show_stats'          "$CONFIG_FILE")
RUN_BUILD=$(jq   -r '.pipeline.build_scene.enabled' "$CONFIG_FILE")
RUN_SYNC=$(jq    -r '.pipeline.rclone_sync.enabled' "$CONFIG_FILE")
SCENE_RELATIVE=$(jq -r '.scene.master_file'        "$CONFIG_FILE")
SCENE_PATH="${SCENE_ROOT}/${SCENE_RELATIVE}"

# --- 3. RUN SCENE BUILDER (if enabled) ---
if [ "$RUN_BUILD" = "true" ]; then
    BUILD_SCRIPT="${SCENE_ROOT}/build_scene.py"
    if [ ! -f "$BUILD_SCRIPT" ]; then
        echo "ERROR: build_scene.py not found in: $SCENE_ROOT"
        exit 1
    fi
    echo "Building scene: $SCENE_NAME"
    python3 "$BUILD_SCRIPT" "$CONFIG_FILE"
    if [ $? -ne 0 ]; then
        echo "ERROR: build_scene.py failed."
        exit 1
    fi
else
    echo "Skipping build_scene.py (disabled in config)."
fi

# --- 4. RUN PROCEDURAL GEOMETRY (if enabled) ---
TREE_ENABLED=$(jq -r '[.scene.trees[]? | select(.enabled == true)] | length > 0' "$CONFIG_FILE")
FOLIAGE_ENABLED=$(jq -r '[.scene.trees[]? | select(.foliage.enabled == true)] | length > 0' "$CONFIG_FILE")
if [ "$TREE_ENABLED" = "true" ] || [ "$FOLIAGE_ENABLED" = "true" ]; then
    GENERATE="${SNAPSHOT_REPO_ROOT}/generate.py"
    if [ ! -f "$GENERATE" ]; then
        echo "ERROR: generate.py not found in repo root."
        exit 1
    fi
    echo "Generating procedural geometry for scene: $SCENE_NAME"
    python3 "$GENERATE" "$CONFIG_FILE"
    if [ $? -ne 0 ]; then
        echo "ERROR: generate.py failed."
        exit 1
    fi
else
    echo "Skipping generate.py (tree and foliage disabled in config)."
fi



# --- 5. VALIDATE SCENE FILE EXISTS ---
if [ ! -f "$SCENE_PATH" ]; then
    echo "ERROR: Scene file not found at: $SCENE_PATH"
    exit 1
fi

# --- 6. BUILD PBRT RUNTIME FLAGS ---
CMD_FLAGS=""
if [ "$USE_GPU"    = "true" ]; then CMD_FLAGS="$CMD_FLAGS --gpu";   fi
if [ "$SHOW_STATS" = "true" ]; then CMD_FLAGS="$CMD_FLAGS --stats"; fi

mkdir -p "$ARCHIVE_DIR"
FINAL_BASE="${ARCHIVE_DIR}/${ARCHIVE_STEM}_${TS}"

# --- 7. RUN PBRT ---
echo "----------------------------------------------------------------"
echo "Rendering scene: $SCENE_NAME"
echo "Scene:     $SCENE_PATH"
echo "Output:    ${FINAL_BASE}.png"
echo "----------------------------------------------------------------"
cd "${SCENE_ROOT}" || exit 1

$PBRT_BIN $CMD_FLAGS --outfile "${FINAL_BASE}.png" "$SCENE_PATH"

if [ $? -ne 0 ]; then
    echo "ERROR: pbrt execution failed."
    exit 1
fi

# The local image is complete at this point. PBRT-v4 Art Studio watches this
# marker so it can display the image while archival and remote sync continue.
echo "ART_STUDIO_RENDER_READY=${FINAL_BASE}.png"

# --- 8. ARCHIVE THE FROZEN REPRODUCIBILITY BUNDLE ---
echo "Archiving reproducibility files..."
python3 "${SNAPSHOT_REPO_ROOT}/render_snapshot.py" finalize \
    --run-directory "$RUN_DIRECTORY" \
    --archive-prefix "$FINAL_BASE" \
    --artifact ".png=${FINAL_BASE}.png" \
    --artifact ".pbrt=${SCENE_PATH}"
if [ $? -ne 0 ]; then
    echo "ERROR: Render completed, but immutable local archive finalization failed."
    echo "       Frozen inputs remain in: $RUN_DIRECTORY"
    exit 1
fi

# --- 9. RCLONE SYNC (if enabled) ---
if [ "$RUN_SYNC" = "true" ]; then
    echo "Syncing archive bundle to Google Drive..."
    rclone copy "$ARCHIVE_DIR" "$REMOTE_PATH" \
        --filter "+ ${ARCHIVE_STEM}_${TS}*" \
        --filter "- **" \
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

python3 "${SNAPSHOT_REPO_ROOT}/render_snapshot.py" cleanup \
    --repository-root "$REPO_ROOT" \
    --run-directory "$RUN_DIRECTORY" || \
    echo "WARNING: Temporary render workspace remains at: $RUN_DIRECTORY"

echo "----------------------------------------------------------------"
echo "Pipeline complete: $SCENE_NAME"
echo "----------------------------------------------------------------"
