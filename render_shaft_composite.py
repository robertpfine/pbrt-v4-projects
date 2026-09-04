#!/usr/bin/env python3
"""Render base and volumetric-shaft passes, then composite them in linear RGB."""

import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime

import numpy as np
from PIL import Image, ImageFilter

from render_snapshot import (
    archive_image_name,
    cleanup_snapshot,
    create_snapshot,
    finalize_snapshot,
    resolve_local_archive,
    scene_files_relative,
)


def load_scene_builder(scene_root):
    path = os.path.join(scene_root, "build_scene.py")
    spec = importlib.util.spec_from_file_location("working_scene_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scale_reflectances(value, scale):
    """Recursively scale configured surface reflectances."""
    def scale_components(components):
        if isinstance(components, list):
            return [scale_components(component) for component in components]
        if isinstance(components, (int, float)):
            return scale * components
        return components

    if isinstance(value, dict):
        for key, child in value.items():
            if "reflectance" in key and isinstance(child, list):
                value[key] = scale_components(child)
            else:
                scale_reflectances(child, scale)
    elif isinstance(value, list):
        for child in value:
            scale_reflectances(child, scale)


def configure_base(cfg, shaft_label):
    result = copy.deepcopy(cfg)
    result["file_names"]["pbrt_scene"] = "scene_base.pbrt"
    shafts = result["scene_description"]["sky"]["sun"]["light_shafts"]
    shafts["aperture"]["enabled"] = False
    if shafts["light"].get("label") == shaft_label:
        shafts["light"]["enabled"] = False
    return result


def configure_shaft(cfg, shaft_label, surface_scale=0.0, terrain_scale=0.0):
    result = copy.deepcopy(cfg)
    result["file_names"]["pbrt_scene"] = "scene_shaft.pbrt"
    sun = result["scene_description"]["sky"]["sun"]
    sun["enabled"] = False
    shaft_light = sun["light_shafts"]["light"]
    shaft_light["enabled"] = shaft_light.get("label") == shaft_label
    scale_reflectances(result["scene_description"]["landforms"], surface_scale)
    scale_reflectances(result["scene_description"]["objects"], surface_scale)
    for index, source in enumerate(cfg["scene_description"]["landforms"]):
        topography = source.get("topography", {})
        if (
            topography.get("enabled", False)
            and topography.get("generator") == "terrain_heightfield"
        ):
            for field in ("surface", "surface_objects"):
                result["scene_description"]["landforms"][index][field] = (
                    copy.deepcopy(source[field])
                )
                scale_reflectances(
                    result["scene_description"]["landforms"][index][field],
                    terrain_scale,
                )
    return result


def render(builder, cfg, scene_root, pbrt, flags, output_path):
    print("Generating scene:", cfg["file_names"]["pbrt_scene"], flush=True)
    medium_rel = builder.write_medium(cfg, scene_root)
    builder.write_scene(cfg, scene_root, medium_rel)
    repository_root = Path(scene_root).resolve().parent
    scene_path = (
        repository_root
        / scene_files_relative(cfg)
        / cfg["file_names"]["pbrt_scene"]
    )
    command = [pbrt, *flags, "--outfile", output_path, scene_path]
    print("Rendering:", output_path, flush=True)
    subprocess.run(command, cwd=scene_root, check=True)


def srgb_to_linear(values):
    return np.where(values <= 0.04045, values / 12.92,
                    ((values + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(values):
    return np.where(values <= 0.0031308, values * 12.92,
                    1.055 * np.maximum(values, 0.0) ** (1.0 / 2.4) - 0.055)


def composite(base_path, shaft_path, output_path, base_opacity, shaft_opacity,
              blur_radius):
    base = Image.open(base_path).convert("RGB")
    shaft = Image.open(shaft_path).convert("RGB")
    if blur_radius > 0:
        shaft = shaft.filter(ImageFilter.GaussianBlur(blur_radius))
    base_linear = srgb_to_linear(np.asarray(base, dtype=np.float32) / 255.0)
    shaft_linear = srgb_to_linear(np.asarray(shaft, dtype=np.float32) / 255.0)
    combined = np.clip(
        base_opacity * base_linear + shaft_opacity * shaft_linear,
        0.0,
        1.0,
    )
    encoded = np.clip(linear_to_srgb(combined), 0.0, 1.0)
    Image.fromarray(np.round(encoded * 255.0).astype(np.uint8), "RGB").save(output_path)


def sync_archive_bundle(prefix, archive, remote_path):
    """Copy one completed composite bundle to its configured remote archive."""
    stem = os.path.basename(prefix)
    command = [
        "rclone", "copy", archive, remote_path,
        "--filter", f"+ {stem}*",
        "--filter", "- **",
        "--drive-chunk-size=64M",
        "--low-level-retries=10",
    ]
    print("Syncing composite bundle to configured remote archive...", flush=True)
    subprocess.run(command, check=True)
    print("Remote composite sync complete.", flush=True)


def pbrt_flags(render_settings):
    """Translate the validated configured backend into PBRT command flags."""

    backend = render_settings["backend"]
    backend_type = backend["type"]
    if backend_type == "gpu":
        flags = ["--gpu"]
    elif backend_type == "cpu":
        flags = []
    else:
        raise ValueError(f"unsupported render backend {backend_type!r}")
    show_statistics = backend["show_statistics"]
    if not isinstance(show_statistics, bool):
        raise ValueError("render backend show_statistics must be boolean")
    if show_statistics:
        flags.append("--stats")
    return flags


def validate_composite_options(options, sky):
    """Reject incomplete or unsafe composite controls before either pass."""

    if not isinstance(options.get("enabled"), bool):
        raise ValueError("shaft_composite.enabled must be boolean")
    shaft_light = options.get("shaft_light")
    labels = {
        light.get("label")
        for light in (
            sky.get("sun", {}),
            sky.get("sun", {}).get("light_shafts", {}).get("light", {}),
        )
        if isinstance(light, dict)
    }
    if not isinstance(shaft_light, str) or shaft_light not in labels:
        raise ValueError("shaft_composite.shaft_light must resolve to a scene light")
    for name in (
        "base_opacity",
        "shaft_opacity",
        "surface_reflectance_scale",
        "terrain_reflectance_scale",
        "blur_radius",
    ):
        value = options.get(name)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"shaft_composite.{name} must be nonnegative")


def activate_snapshot(repository_root, config_path):
    """Re-execute this entry point from an immutable source/config snapshot."""

    active_run = os.environ.get("PBRT_RENDER_SNAPSHOT_DIR")
    if active_run:
        return (
            Path(os.environ["PBRT_LIVE_REPOSITORY_ROOT"]).resolve(),
            Path(active_run).resolve(),
            os.environ["PBRT_RENDER_TIMESTAMP"],
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result = create_snapshot(Path(repository_root), Path(config_path), timestamp)
    print("Render inputs frozen:", result["run_directory"], flush=True)
    environment = os.environ.copy()
    environment["PBRT_RENDER_SNAPSHOT_DIR"] = result["run_directory"]
    environment["PBRT_LIVE_REPOSITORY_ROOT"] = str(Path(repository_root).resolve())
    environment["PBRT_RENDER_TIMESTAMP"] = timestamp
    snapshot_script = Path(result["repository_root"]) / "render_shaft_composite.py"
    os.execve(
        sys.executable,
        [sys.executable, str(snapshot_script), result["config"]],
        environment,
    )
    raise AssertionError("os.execve returned unexpectedly")


def main():
    repository_root = os.path.dirname(os.path.abspath(__file__))
    config_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.path.join(repository_root, "scene_workspace", "config.json")
    )
    if os.path.isdir(config_path):
        config_path = os.path.join(config_path, "config.json")
    config_path = os.path.abspath(config_path)
    live_repository_root, run_directory, stamp = activate_snapshot(
        repository_root, config_path
    )
    repository_root = os.path.dirname(os.path.abspath(__file__))
    scene_root = os.path.dirname(config_path)
    with open(config_path, "r") as handle:
        cfg = json.load(handle)

    render_settings = cfg["render_settings"]
    options = render_settings["shaft_composite"]
    validate_composite_options(options, cfg["scene_description"]["sky"])
    shaft_label = options["shaft_light"]
    pbrt = cfg["file_paths"]["pbrt_executable"]
    flags = pbrt_flags(render_settings)

    archive = resolve_local_archive(cfg, Path(live_repository_root))
    os.makedirs(archive, exist_ok=True)
    configured_image = archive / archive_image_name(cfg, stamp)
    prefix = str(configured_image.with_suffix(""))
    base_path = prefix + "_base.png"
    shaft_path = prefix + "_shaft.png"
    composite_path = prefix + "_composite.png"

    builder = load_scene_builder(scene_root)
    render(builder, configure_base(cfg, shaft_label), scene_root,
           pbrt, flags, base_path)
    render(builder, configure_shaft(
               cfg,
               shaft_label,
               float(options["surface_reflectance_scale"]),
               float(options["terrain_reflectance_scale"]),
           ), scene_root,
           pbrt, flags, shaft_path)
    composite(base_path, shaft_path, composite_path,
              float(options["base_opacity"]),
              float(options["shaft_opacity"]),
              float(options["blur_radius"]))
    finalize_snapshot(
        run_directory,
        Path(prefix),
        (
            ("_base.png", Path(base_path)),
            ("_shaft.png", Path(shaft_path)),
            ("_composite.png", Path(composite_path)),
            (
                "_base.pbrt",
                Path(repository_root)
                / scene_files_relative(cfg)
                / "scene_base.pbrt",
            ),
            (
                "_shaft.pbrt",
                Path(repository_root)
                / scene_files_relative(cfg)
                / "scene_shaft.pbrt",
            ),
            (
                "_render_shaft_composite.py",
                Path(repository_root) / "render_shaft_composite.py",
            ),
            (
                "_shaft-compositing.md",
                Path(repository_root) / "docs" / "shaft-compositing.md",
            ),
        ),
    )
    try:
        sync_archive_bundle(
            prefix,
            archive,
            cfg["file_paths"]["remote_archive"],
        )
    except subprocess.CalledProcessError:
        print(
            "WARNING: Composite succeeded locally, but remote archive sync failed.",
            flush=True,
        )
        print("         Files are preserved in:", archive, flush=True)
    cleanup_snapshot(live_repository_root, run_directory)
    print("Composite complete:", composite_path, flush=True)


if __name__ == "__main__":
    main()
