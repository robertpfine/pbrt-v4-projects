#!/usr/bin/env bash
# Start PBRT-v4 Art Studio from the repository-local Python environment when
# available. This script never installs or modifies dependencies.

set -e

STUDIO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STUDIO_PYTHON="${STUDIO_ROOT}/.venv/bin/python"

if [ ! -x "$STUDIO_PYTHON" ]; then
    STUDIO_PYTHON="python3"
fi

exec "$STUDIO_PYTHON" "${STUDIO_ROOT}/pbrt_v4_art_studio.py" "$@"
