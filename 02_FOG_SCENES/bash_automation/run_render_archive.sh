#!/bin/bash

# 1. Define variables for naming and timestamping
SCENE_PATH="/home/rpf4/my-pbrt-projects/02_FOG_SCENES/scenes/fog1-v4.pbrt"
#RENDER_PATH="/home/rpf4/my-pbrt-projects/02_FOG_SCENES/renders/fog1-v4.png"
HISTORY_DIR="/home/rpf4/my-pbrt-projects/02_FOG_SCENES/history"
TS=$(date +%Y%m%d_%H%M%S)

# 2. Define the FINAL destination name
# This puts the timestamped name directly into the history folder
FINAL_RENDER="${HISTORY_DIR}/fog_${TS}.png"
FINAL_SCENE="${HISTORY_DIR}/fog_${TS}.pbrt"


# 3. Run the PBRT-v4 GPU render
# Uses the specific build path and --gpu flag from your verified command
/home/rpf4/pbrt-v4/build/pbrt --gpu --stats --outfile "$FINAL_RENDER" "$SCENE_PATH"

# 4. Archive the Scene Code
# We copy the code to match the image timestamp
cp "$SCENE_PATH" "$FINAL_SCENE"

echo "------------------------------------------------"
echo "Rendered and Archived to: $FINAL_RENDER"
echo "------------------------------------------------"