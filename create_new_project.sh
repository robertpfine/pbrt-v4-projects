#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: ./create_new_project.sh PROJECT_NAME"
    exit 1
fi

PROJECT_NAME=$1
BASE_DIR="/home/rpf4/my-pbrt-projects/${PROJECT_NAME}"

echo "Creating project structure for: ${PROJECT_NAME}..."

# 1. Create the standardized directory tree
mkdir -p "${BASE_DIR}/bash_automation"
mkdir -p "${BASE_DIR}/scene_files"
mkdir -p "${BASE_DIR}/misc"

# 2. Deploy the universal 'render_and_archive.sh' template
cat << 'EOF' > "${BASE_DIR}/bash_automation/render_and_archive.sh"
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
EOF

chmod +x "${BASE_DIR}/bash_automation/render_and_archive.sh"

echo "Success! Project ${PROJECT_NAME} is ready at ${BASE_DIR}"


#Whenever you start a new study (e.g., "03_REFRACTION_TESTS"), 
#run this from the root:  chmod +x create_new_project.sh
#./create_new_project.sh 03_REFRACTION_TESTS

#New Projects: Run ./create_new_project.sh [Name] from your root directory.

#Rendering: Run the render_and_archive.sh script inside that project's bash_automation folder.

#Redundancy: Your 2TB Linux drive and your Google Drive will stay perfectly in sync without you typing another rclone command.