#!/usr/bin/env python3
"""Render base and volumetric-shaft passes, then composite them in linear RGB."""

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime

import numpy as np
from PIL import Image, ImageFilter


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
    result["scene"]["master_file"] = "scene_files/scene_base.pbrt"
    result["scene"]["sun_aperture"]["enabled"] = False
    for light in result["scene"].get("lights", []):
        if light.get("label") == shaft_label:
            light["enabled"] = False
    return result


def configure_shaft(cfg, shaft_label, surface_scale=0.0, terrain_scale=0.0):
    result = copy.deepcopy(cfg)
    result["scene"]["master_file"] = "scene_files/scene_shaft.pbrt"
    for light in result["scene"].get("lights", []):
        light["enabled"] = light.get("label") == shaft_label
    scale_reflectances(result["scene"], surface_scale)
    result["scene"]["landscape"]["ground"] = copy.deepcopy(
        cfg["scene"]["landscape"]["ground"]
    )
    scale_reflectances(result["scene"]["landscape"]["ground"], terrain_scale)
    return result


def render(builder, cfg, scene_root, pbrt, flags, output_path):
    print("Generating scene:", cfg["scene"]["master_file"], flush=True)
    medium_rel = builder.write_medium(cfg, scene_root)
    builder.write_scene(cfg, scene_root, medium_rel)
    scene_path = os.path.join(scene_root, cfg["scene"]["master_file"])
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


def archive_supporting_files(prefix, repository_root, scene_root):
    """Preserve the inputs needed to reproduce a composite render."""
    sources = {
        os.path.join(scene_root, "config.json"): prefix + "_config.json",
        os.path.join(scene_root, "build_scene.py"): prefix + "_build_scene.py",
        os.path.join(repository_root, "render_pipeline.sh"):
            prefix + "_render_pipeline.sh",
        os.path.join(repository_root, "render_shaft_composite.py"):
            prefix + "_render_shaft_composite.py",
        os.path.join(scene_root, "scene_files", "scene_base.pbrt"):
            prefix + "_base.pbrt",
        os.path.join(scene_root, "scene_files", "scene_shaft.pbrt"):
            prefix + "_shaft.pbrt",
        os.path.join(repository_root, "docs", "shaft-compositing.md"):
            prefix + "_shaft-compositing.md",
    }
    for source, destination in sources.items():
        shutil.copy2(source, destination)


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
    print("Syncing composite bundle to Google Drive...", flush=True)
    subprocess.run(command, check=True)
    print("Google Drive composite sync complete.", flush=True)


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
    scene_root = os.path.dirname(config_path)
    with open(config_path, "r") as handle:
        cfg = json.load(handle)

    options = cfg["pipeline"]["shaft_composite"]
    shaft_label = options.get("shaft_light", "shaft_sun")
    pbrt = cfg["runtime"]["pbrt_binary"]
    flags = []
    if cfg["runtime"].get("use_gpu", False):
        flags.append("--gpu")
    if cfg["runtime"].get("show_stats", False):
        flags.append("--stats")

    archive = os.path.join(repository_root, "Archive")
    os.makedirs(archive, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scene_name = cfg["scene"].get("name", "untitled_scene")
    archive_stem = "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in scene_name
    )
    prefix = os.path.join(archive, f"{archive_stem}_{stamp}")
    base_path = prefix + "_base.png"
    shaft_path = prefix + "_shaft.png"
    composite_path = prefix + "_composite.png"

    builder = load_scene_builder(scene_root)
    render(builder, configure_base(cfg, shaft_label), scene_root,
           pbrt, flags, base_path)
    render(builder, configure_shaft(
               cfg,
               shaft_label,
               float(options.get("surface_reflectance_scale", 0.0)),
               float(options.get("terrain_reflectance_scale", 0.0)),
           ), scene_root,
           pbrt, flags, shaft_path)
    composite(base_path, shaft_path, composite_path,
              float(options.get("base_opacity", 1.0)),
              float(options.get("shaft_opacity", 0.65)),
              float(options.get("blur_radius", 1.0)))
    archive_supporting_files(prefix, repository_root, scene_root)
    sync_options = cfg.get("pipeline", {}).get("rclone_sync", {})
    if sync_options.get("enabled", False):
        sync_archive_bundle(
            prefix,
            archive,
            cfg["archive"]["remote_path"],
        )
    print("Composite complete:", composite_path, flush=True)


if __name__ == "__main__":
    main()
