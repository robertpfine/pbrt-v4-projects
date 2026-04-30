#!/bin/bash

# 1. SETUP & INPUT
FILE_INPUT=$1
MODE=$2
ARCHIVE_DIR="$HOME/my-pbrt-projects/Archive"
LOG_FILE="$HOME/my-pbrt-projects/render_log.txt"
TIMESTAMP=$(date +"%m%d_%H%M")

# 2. SMART SEARCH: Find the file if a full path wasn't given
if [[ "$FILE_INPUT" == *"/"* ]]; then
    # If the user provided a path (like folder/file.pbrt), use it
    SCENE_PATH="$FILE_INPUT"
else
    # Search for the file within my-pbrt-projects
    echo "Searching for $FILE_INPUT..."
    SCENE_PATH=$(find ~/my-pbrt-projects -name "$FILE_INPUT" -not -path "*/Archive/*" | head -n 1)
fi

# 3. VALIDATION: Did we find it?
if [ -z "$SCENE_PATH" ] || [ ! -f "$SCENE_PATH" ]; then
    echo "Error: Could not find '$FILE_INPUT'. Please check the spelling."
    exit 1
fi

# 4. IDENTITY: Extract Project and Filename for the Archive
# This extracts the folder name (e.g., 02_FOG_SCENES) even if found via search
PROJECT_NAME=$(echo "$SCENE_PATH" | rev | cut -d'/' -f3 | rev)
SCENE_BASE=$(basename "$SCENE_PATH" .pbrt)
FINAL_ID="${PROJECT_NAME}_${SCENE_BASE}_${TIMESTAMP}"

# 5. THE CORE ENGINE
run_task() {
    echo "--- Rendering $FINAL_ID ---"
    ~/pbrt-v4/build/pbrt --gpu --stats "$SCENE_PATH" --outfile "$ARCHIVE_DIR/$FINAL_ID.png"
    cp "$SCENE_PATH" "$ARCHIVE_DIR/$FINAL_ID.pbrt"
    echo "--- Syncing to Google Drive ---"
    rclone copy "$ARCHIVE_DIR" "gdrive:wipImages/pbrt-v4" --include "$FINAL_ID.*"
    notify-send "Render Complete" "$FINAL_ID has been archived and synced." --icon=image-x-generic
    echo "--- Finished: $FINAL_ID ---"
}

# 6. EXECUTION
if [ "$MODE" == "-b" ]; then
    echo "Found: $SCENE_PATH"
    echo "Submitting to background. Log: tail -f render_log.txt"
    run_task > "$LOG_FILE" 2>&1 &
else
    echo "Found: $SCENE_PATH"
    run_task
fi