#!/usr/bin/env bash
# Launch the PBRT pipeline in the host GNOME Terminal from Snap-packaged VS Code.

set -u

REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PBRT_ART_CONFIG="${1:-${REPOSITORY_ROOT}/scene_workspace/config.json}"
export PBRT_ART_CONFIG

# VS Code is installed as a Snap and exports its private GTK/GIO paths into
# child processes. A host GNOME Terminal launched with those paths can load
# Core20 libraries beside the host glibc and fail before opening. Remove only
# the Snap desktop/runtime variables; retain DISPLAY, D-Bus, CUDA, and PATH for
# the actual render process.
unset GDK_PIXBUF_MODULEDIR
unset GDK_PIXBUF_MODULE_FILE
unset GIO_MODULE_DIR
unset GSETTINGS_SCHEMA_DIR
unset GTK_EXE_PREFIX
unset GTK_IM_MODULE_FILE
unset GTK_PATH
unset LOCPATH
unset SNAP
unset SNAP_ARCH
unset SNAP_COMMON
unset SNAP_CONTEXT
unset SNAP_COOKIE
unset SNAP_DATA
unset SNAP_EUID
unset SNAP_INSTANCE_NAME
unset SNAP_LAUNCHER_ARCH_TRIPLET
unset SNAP_LIBRARY_PATH
unset SNAP_NAME
unset SNAP_REAL_HOME
unset SNAP_REVISION
unset SNAP_UID
unset SNAP_USER_COMMON
unset SNAP_USER_DATA
unset SNAP_VERSION
unset XDG_DATA_HOME

if [[ -n "${XDG_DATA_DIRS_VSCODE_SNAP_ORIG:-}" ]]; then
    export XDG_DATA_DIRS="${XDG_DATA_DIRS_VSCODE_SNAP_ORIG}"
fi
unset XDG_DATA_DIRS_VSCODE_SNAP_ORIG

exec /usr/bin/gnome-terminal \
    --wait \
    --title="PBRT-v4 Art Studio — Render Log" \
    --working-directory="${REPOSITORY_ROOT}" \
    -- bash -lc '
        ./render_pipeline.sh "$PBRT_ART_CONFIG"
        render_status=$?
        printf "\nRender process exited with status %s. This terminal will remain open.\n" "$render_status"
        exec bash
    '
