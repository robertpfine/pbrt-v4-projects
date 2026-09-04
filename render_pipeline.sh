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
SCENE_FILES=$(printf '%s' "$SNAPSHOT_INFO" | jq -r '.scene_files')
SNAPSHOT_REPO_ROOT=$(printf '%s' "$SNAPSHOT_INFO" | jq -r '.repository_root')
RUN_DIRECTORY=$(printf '%s' "$SNAPSHOT_INFO" | jq -r '.run_directory')
ARCHIVE_DIR=$(printf '%s' "$SNAPSHOT_INFO" | jq -r '.archive_directory')
FINAL_IMAGE=$(printf '%s' "$SNAPSHOT_INFO" | jq -r '.archive_image')
echo "Render inputs frozen: $RUN_DIRECTORY"

# --- 2. PARSE CONFIG VIA JQ ---
SCENE_NAME=$(jq -r '.scene_description.name' "$CONFIG_FILE")
REMOTE_PATH=$(jq -r '.file_paths.remote_archive'   "$CONFIG_FILE")
PBRT_BIN=$(jq    -r '.file_paths.pbrt_executable'  "$CONFIG_FILE")
BACKEND_TYPE=$(jq -r '.render_settings.backend.type' "$CONFIG_FILE")
SHOW_STATS=$(jq -r '.render_settings.backend.show_statistics' "$CONFIG_FILE")
SHAFT_COMPOSITE=$(jq -r '.render_settings.shaft_composite.enabled' "$CONFIG_FILE")
SCENE_FILENAME=$(jq -r '.file_names.pbrt_scene'    "$CONFIG_FILE")
SCENE_PATH="${SCENE_FILES}/${SCENE_FILENAME}"

CMD_FLAGS=""
if [ "$BACKEND_TYPE" = "gpu" ]; then
    CMD_FLAGS="$CMD_FLAGS --gpu"
elif [ "$BACKEND_TYPE" != "cpu" ]; then
    echo "ERROR: Unsupported render backend: $BACKEND_TYPE"
    exit 1
fi
if [ "$SHOW_STATS" = "true" ]; then
    CMD_FLAGS="$CMD_FLAGS --stats"
elif [ "$SHOW_STATS" != "false" ]; then
    echo "ERROR: render_settings.backend.show_statistics must be boolean."
    exit 1
fi
if [ "$SHAFT_COMPOSITE" != "true" ] && [ "$SHAFT_COMPOSITE" != "false" ]; then
    echo "ERROR: render_settings.shaft_composite.enabled must be boolean."
    exit 1
fi

# A composite render reuses this already-frozen transaction rather than
# creating a second timestamp or reading mutable live settings.
if [ "$SHAFT_COMPOSITE" = "true" ]; then
    COMPOSITE_SCRIPT="${SNAPSHOT_REPO_ROOT}/render_shaft_composite.py"
    if [ ! -f "$COMPOSITE_SCRIPT" ]; then
        echo "ERROR: render_shaft_composite.py not found in frozen repository."
        exit 1
    fi
    export PBRT_RENDER_SNAPSHOT_DIR="$RUN_DIRECTORY"
    export PBRT_LIVE_REPOSITORY_ROOT="$REPO_ROOT"
    export PBRT_RENDER_TIMESTAMP="$TS"
    exec python3 "$COMPOSITE_SCRIPT" "$CONFIG_FILE"
fi

# --- 3. RUN REQUIRED SCENE BUILDER ---
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

# --- 4. RUN PROCEDURAL GEOMETRY (if enabled) ---
TREE_ENABLED=$(jq -r '[.scene_description.landforms[]?.surface_objects[]? | select(.generator == "space_colonization_tree" and .enabled == true)] | length > 0' "$CONFIG_FILE")
FOLIAGE_ENABLED=$(jq -r '[.scene_description.landforms[]?.surface_objects[]? | select(.generator == "space_colonization_tree" and .construction.foliage.enabled == true)] | length > 0' "$CONFIG_FILE")
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

mkdir -p "$ARCHIVE_DIR"
FINAL_BASE="${FINAL_IMAGE%.png}"
ARCHIVE_PREFIX=$(basename "$FINAL_BASE")

# --- 7. RUN PBRT ---
echo "----------------------------------------------------------------"
echo "Rendering scene: $SCENE_NAME"
echo "Scene:     $SCENE_PATH"
echo "Output:    ${FINAL_BASE}.png"
echo "----------------------------------------------------------------"
cd "${SCENE_ROOT}" || exit 1

$PBRT_BIN $CMD_FLAGS --outfile "$FINAL_IMAGE" "$SCENE_PATH"

if [ $? -ne 0 ]; then
    echo "ERROR: pbrt execution failed."
    exit 1
fi

# The local image is complete at this point. PBRT-v4 Art Studio watches this
# marker so it can display the image while archival and remote sync continue.
echo "ART_STUDIO_RENDER_READY=${FINAL_IMAGE}"

# --- 8. ARCHIVE THE FROZEN REPRODUCIBILITY BUNDLE ---
echo "Archiving reproducibility files..."
python3 "${SNAPSHOT_REPO_ROOT}/render_snapshot.py" finalize \
    --run-directory "$RUN_DIRECTORY" \
    --archive-prefix "$FINAL_BASE" \
    --artifact ".png=${FINAL_IMAGE}" \
    --artifact ".pbrt=${SCENE_PATH}"
if [ $? -ne 0 ]; then
    echo "ERROR: Render completed, but immutable local archive finalization failed."
    echo "       Frozen inputs remain in: $RUN_DIRECTORY"
    exit 1
fi

# --- 9. RCLONE SYNC ---
echo "Syncing archive bundle to configured remote archive..."
rclone copy "$ARCHIVE_DIR" "$REMOTE_PATH" \
    --filter "+ ${ARCHIVE_PREFIX}*" \
    --filter "- **" \
    --drive-chunk-size=64M \
    --low-level-retries=5

if [ $? -eq 0 ]; then
    echo "Remote archive sync complete."
else
    echo "WARNING: Render succeeded locally, but remote archive sync failed."
    echo "         Files are preserved in: $ARCHIVE_DIR"
fi

python3 "${SNAPSHOT_REPO_ROOT}/render_snapshot.py" cleanup \
    --repository-root "$REPO_ROOT" \
    --run-directory "$RUN_DIRECTORY" || \
    echo "WARNING: Temporary render workspace remains at: $RUN_DIRECTORY"

echo "----------------------------------------------------------------"
echo "Pipeline complete: $SCENE_NAME"
echo "----------------------------------------------------------------"
