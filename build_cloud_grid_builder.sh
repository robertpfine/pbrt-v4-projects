#!/usr/bin/env bash
set -eu

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIRECTORY="${REPO_ROOT}/build/cloud_grid_builder"
OUTPUT="${OUTPUT_DIRECTORY}/cloud_grid_builder"

mkdir -p "$OUTPUT_DIRECTORY"
g++ -std=c++17 -O3 -pthread \
    "${REPO_ROOT}/cpp/cloud_grid_builder.cpp" \
    -ldl \
    -o "$OUTPUT"

echo "$OUTPUT"
