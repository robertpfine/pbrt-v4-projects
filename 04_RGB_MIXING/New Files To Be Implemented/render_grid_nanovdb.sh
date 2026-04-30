#!/bin/bash
############################################################
# PROJECT: 04_RGB_MIXING
# FILE: render_grid_nanovdb.sh
# VERSION: NanoVDB UniformGrid Pipeline
#
# Reads config_grid_nanovdb.json and:
#   1. Generates density.bin (Perlin noise or constant)
#   2. Converts to density.nvdb
#   3. Writes noise_grid_nvdb_XXXXXX.pbrt (medium block)
#   4. Writes 04_grid_render_XXXXXX.pbrt (scene file)
#   5. Renders and archives image, scene, medium, and nvdb
#   6. Syncs to Google Drive
#
# Override flags in config: set "override": true for any
# block to skip generation and use the existing .pbrt content.
############################################################

# --- 1. PATHS ---
SCRIPT_PATH=$(readlink -f "$0")
BASH_DIR=$(dirname "$SCRIPT_PATH")
PROJECT_DIR=$(dirname "$BASH_DIR")
ARCHIVE_DIR="$(dirname "$PROJECT_DIR")/Archive"
SCENE_DIR="${PROJECT_DIR}/scene_files"
VOLUMES_DIR="${PROJECT_DIR}/volumes"
CONFIG="${BASH_DIR}/config_grid_nanovdb.json"
MAKE_NVDB="${BASH_DIR}/make_nvdb"
GEN_DENSITY="${SCENE_DIR}/gen_density.py"
MEDIUM_FILE="${SCENE_DIR}/noise_grid_nvdb_XXXXXX.pbrt"
SCENE_FILE="${SCENE_DIR}/04_grid_render_XXXXXX.pbrt"
DENSITY_BIN="${SCENE_DIR}/density.bin"
DENSITY_NVDB="${VOLUMES_DIR}/density.nvdb"

# --- 2. CHECK DEPENDENCIES ---
if [ ! -f "$CONFIG" ]; then
    echo "ERROR: Config not found: $CONFIG"; exit 1
fi
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found"; exit 1
fi
if ! command -v jq &>/dev/null; then
    echo "ERROR: jq not found. Install with: sudo apt install jq"; exit 1
fi

# --- 3. READ CONFIG ---
PBRT_BIN=$(jq -r '.project.pbrt_bin' "$CONFIG")
PROJECT_TITLE=$(jq -r '.project.title' "$CONFIG")
SCENE_NAME=$(jq -r '.project.scene_name' "$CONFIG")
REMOTE_PATH=$(jq -r '.project.remote_path' "$CONFIG")

GRID_OVERRIDE=$(jq -r '.grid.override' "$CONFIG")
MEDIUM_OVERRIDE=$(jq -r '.medium.override' "$CONFIG")
CAMERA_OVERRIDE=$(jq -r '.camera.override' "$CONFIG")
CONTAINER_OVERRIDE=$(jq -r '.container.override' "$CONFIG")
LIGHTS_OVERRIDE=$(jq -r '.lights.override' "$CONFIG")
RENDER_OVERRIDE=$(jq -r '.render.override' "$CONFIG")

ARCHIVE_NVDB=$(jq -r '.archive.archive_density_nvdb' "$CONFIG")
ARCHIVE_MEDIUM=$(jq -r '.archive.archive_medium_pbrt' "$CONFIG")

# --- 4. GENERATE GRID (unless override) ---
if [ "$GRID_OVERRIDE" = "false" ]; then
    echo "Generating density grid..."
    NX=$(jq -r '.grid.nx' "$CONFIG")
    NY=$(jq -r '.grid.ny' "$CONFIG")
    NZ=$(jq -r '.grid.nz' "$CONFIG")
    SOURCE=$(jq -r '.grid.source' "$CONFIG")
    NOISE_SCALE=$(jq -r '.grid.noise_scale' "$CONFIG")
    CONSTANT_DENSITY=$(jq -r '.grid.constant_density' "$CONFIG")

    python3 "$GEN_DENSITY" \
        --nx "$NX" --ny "$NY" --nz "$NZ" \
        --source "$SOURCE" \
        --scale "$NOISE_SCALE" \
        --constant "$CONSTANT_DENSITY" \
        --out "$DENSITY_BIN"

    if [ $? -ne 0 ]; then echo "ERROR: gen_density.py failed"; exit 1; fi

    echo "Converting to NanoVDB..."
    "$MAKE_NVDB" "$DENSITY_BIN" "$DENSITY_NVDB"
    if [ $? -ne 0 ]; then echo "ERROR: make_nvdb failed"; exit 1; fi
else
    echo "Grid override: using existing density.nvdb"
fi

# --- 5. WRITE MEDIUM FILE (unless override) ---
if [ "$MEDIUM_OVERRIDE" = "false" ]; then
    echo "Writing medium file..."
    MEDIUM_NAME=$(jq -r '.medium.name' "$CONFIG")
    SIGMA_S_R=$(jq -r '.medium.sigma_s[0]' "$CONFIG")
    SIGMA_S_G=$(jq -r '.medium.sigma_s[1]' "$CONFIG")
    SIGMA_S_B=$(jq -r '.medium.sigma_s[2]' "$CONFIG")
    SIGMA_A_R=$(jq -r '.medium.sigma_a[0]' "$CONFIG")
    SIGMA_A_G=$(jq -r '.medium.sigma_a[1]' "$CONFIG")
    SIGMA_A_B=$(jq -r '.medium.sigma_a[2]' "$CONFIG")
    G=$(jq -r '.medium.g' "$CONFIG")

    # Path to nvdb relative to scene_files
    NVDB_REL="../volumes/density.nvdb"

    cat > "$MEDIUM_FILE" << EOF
MakeNamedMedium "${MEDIUM_NAME}"
    "string type"     [ "nanovdb" ]
    "string filename" [ "${NVDB_REL}" ]
    "rgb sigma_s"     [ ${SIGMA_S_R} ${SIGMA_S_G} ${SIGMA_S_B} ]
    "rgb sigma_a"     [ ${SIGMA_A_R} ${SIGMA_A_G} ${SIGMA_A_B} ]
    "float g"         [ ${G} ]
EOF
else
    echo "Medium override: using existing ${MEDIUM_FILE}"
fi

# --- 6. WRITE SCENE FILE (unless individual block overrides) ---
echo "Writing scene file..."

# Read render block
if [ "$RENDER_OVERRIDE" = "false" ]; then
    INTEGRATOR=$(jq -r '.render.integrator' "$CONFIG")
    MAX_DEPTH=$(jq -r '.render.max_depth' "$CONFIG")
    SAMPLER=$(jq -r '.render.sampler' "$CONFIG")
    SPP=$(jq -r '.render.spp' "$CONFIG")
    RES_X=$(jq -r '.render.resolution_x' "$CONFIG")
    RES_Y=$(jq -r '.render.resolution_y' "$CONFIG")
fi

# Read camera block
if [ "$CAMERA_OVERRIDE" = "false" ]; then
    CAM_X=$(jq -r '.camera.position[0]' "$CONFIG")
    CAM_Y=$(jq -r '.camera.position[1]' "$CONFIG")
    CAM_Z=$(jq -r '.camera.position[2]' "$CONFIG")
    LOOK_X=$(jq -r '.camera.look_at[0]' "$CONFIG")
    LOOK_Y=$(jq -r '.camera.look_at[1]' "$CONFIG")
    LOOK_Z=$(jq -r '.camera.look_at[2]' "$CONFIG")
    UP_X=$(jq -r '.camera.up[0]' "$CONFIG")
    UP_Y=$(jq -r '.camera.up[1]' "$CONFIG")
    UP_Z=$(jq -r '.camera.up[2]' "$CONFIG")
    FOV=$(jq -r '.camera.fov' "$CONFIG")
fi

# Read container block
if [ "$CONTAINER_OVERRIDE" = "false" ]; then
    RADIUS=$(jq -r '.container.radius' "$CONFIG")
    MEDIUM_NAME=$(jq -r '.medium.name' "$CONFIG")
fi

# Build lights section
LIGHTS_SECTION=""
if [ "$LIGHTS_OVERRIDE" = "false" ]; then
    INFINITE_ENABLED=$(jq -r '.lights.infinite.enabled' "$CONFIG")
    if [ "$INFINITE_ENABLED" = "true" ]; then
        INF_R=$(jq -r '.lights.infinite.color[0]' "$CONFIG")
        INF_G=$(jq -r '.lights.infinite.color[1]' "$CONFIG")
        INF_B=$(jq -r '.lights.infinite.color[2]' "$CONFIG")
        LIGHTS_SECTION+="    LightSource \"infinite\" \"rgb L\" [ ${INF_R} ${INF_G} ${INF_B} ]\n"
    fi

    NUM_POINTS=$(jq '.lights.points | length' "$CONFIG")
    for i in $(seq 0 $((NUM_POINTS - 1))); do
        PR=$(jq -r ".lights.points[${i}].color[0]" "$CONFIG")
        PG=$(jq -r ".lights.points[${i}].color[1]" "$CONFIG")
        PB=$(jq -r ".lights.points[${i}].color[2]" "$CONFIG")
        PX=$(jq -r ".lights.points[${i}].position[0]" "$CONFIG")
        PY=$(jq -r ".lights.points[${i}].position[1]" "$CONFIG")
        PZ=$(jq -r ".lights.points[${i}].position[2]" "$CONFIG")
        LIGHTS_SECTION+="    LightSource \"point\" \"rgb I\" [ ${PR} ${PG} ${PB} ] \"point3 from\" [ ${PX} ${PY} ${PZ} ]\n"
    done
else
    echo "Lights override: using existing lights in scene file"
    # Extract existing lights block from scene file if it exists
    if [ -f "$SCENE_FILE" ]; then
        LIGHTS_SECTION=$(sed -n '/# --- LIGHTING ---/,/^$/p' "$SCENE_FILE")
    fi
fi

# Write the scene file
cat > "$SCENE_FILE" << EOF
############################################################
# PROJECT: ${PROJECT_TITLE}
# FILE: 04_grid_render_XXXXXX.pbrt
# VERSION: pbrt-v4 (NANOVDB GRID)
# CONFIG: config_grid_nanovdb.json
############################################################

Integrator "${INTEGRATOR}" "integer maxdepth" [${MAX_DEPTH}]
Sampler "${SAMPLER}" "integer pixelsamples" [${SPP}]
Film "rgb" "integer xresolution" [${RES_X}] "integer yresolution" [${RES_Y}]
    "string filename" ["grid_test.exr"]

LookAt ${CAM_X} ${CAM_Y} ${CAM_Z}  ${LOOK_X} ${LOOK_Y} ${LOOK_Z}  ${UP_X} ${UP_Y} ${UP_Z}
Camera "perspective" "float fov" [${FOV}]

WorldBegin
    # --- INCLUDE THE NANOVDB MEDIUM ---
    Include "noise_grid_nvdb_XXXXXX.pbrt"

    # --- DEFINE THE CONTAINER ---
    AttributeBegin
        MediumInterface "${MEDIUM_NAME}" ""
        Material "interface"
        Shape "sphere" "float radius" ${RADIUS}
    AttributeEnd

    # --- LIGHTING ---
$(echo -e "$LIGHTS_SECTION")
EOF

echo "Scene file written."

# --- 7. RENDER ---
TS=$(date +%Y%m%d_%H%M%S)
FINAL_BASE="${ARCHIVE_DIR}/${PROJECT_TITLE}_${TS}"

echo "Starting GPU render for: ${SCENE_NAME}..."
"$PBRT_BIN" --gpu --stats --outfile "${FINAL_BASE}.png" "$SCENE_FILE"
if [ $? -ne 0 ]; then echo "ERROR: pbrt render failed"; exit 1; fi

# --- 8. ARCHIVE ---
echo "Archiving..."

# Archive scene file with updated header
cp "$SCENE_FILE" "${FINAL_BASE}.pbrt"
sed -i "s/^# FILE:.*/# FILE: ${SCENE_NAME}/" "${FINAL_BASE}.pbrt"
sed -i "s/^# PROJECT:.*/# PROJECT: ${PROJECT_TITLE}/" "${FINAL_BASE}.pbrt"

# Archive medium file
#if [ "$ARCHIVE_MEDIUM" = "true" ]; then
#    cp "$MEDIUM_FILE" "${FINAL_BASE}_NANO.pbrt"
#fi

# Archive nvdb
if [ "$ARCHIVE_NVDB" = "true" ]; then
    cp "$DENSITY_NVDB" "${FINAL_BASE}.nvdb"
fi

# --- 9. SYNC ---
echo "Syncing to Google Drive..."
rclone copy "$ARCHIVE_DIR" "$REMOTE_PATH"

echo "------------------------------------------------"
echo "Success: Rendered and Archived to ${FINAL_BASE}.png"
echo "------------------------------------------------"
