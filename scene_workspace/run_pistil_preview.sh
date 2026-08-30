#!/usr/bin/env bash
set -o pipefail

cd /home/rpf4/my-pbrt-projects/scene_workspace || exit 1
python3 pistil_preview.py || exit 1

timestamp=$(date +%Y%m%d_%H%M%S)
output="../Archive/pistil_preview_${timestamp}.png"
log="../Archive/pistil_preview_${timestamp}.log"
/home/rpf4/pbrt-v4/build/pbrt \
  --gpu \
  --outfile "$output" \
  scene_files/pistil_preview.pbrt \
  2>&1 | tee "$log"
status=${PIPESTATUS[0]}
echo "Render exit status: $status"
echo "Image: $output"
echo "Log: $log"
exec bash
