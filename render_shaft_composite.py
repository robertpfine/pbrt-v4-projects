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


def load_scene_builder(project_root):
    path = os.path.join(project_root, "build_scene.py")
    spec = importlib.util.spec_from_file_location("project_build_scene", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scale_reflectances(value, scale):
    """Recursively scale configured surface reflectances."""
    if isinstance(value, dict):
        for key, child in value.items():
            if "reflectance" in key and isinstance(child, list):
                value[key] = [scale * component for component in child]
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
    result["scene"]["terrain"] = copy.deepcopy(cfg["scene"]["terrain"])
    scale_reflectances(result["scene"]["terrain"], terrain_scale)
    return result


def render(builder, cfg, project_root, pbrt, flags, output_path):
    medium_rel = builder.write_medium(cfg, project_root)
    builder.write_scene(cfg, project_root, medium_rel)
    scene_path = os.path.join(project_root, cfg["scene"]["master_file"])
    command = [pbrt, *flags, "--outfile", output_path, scene_path]
    print("Rendering:", output_path, flush=True)
    subprocess.run(command, cwd=project_root, check=True)


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


def archive_supporting_files(prefix, repository_root, project_root):
    """Preserve the inputs needed to reproduce a composite render."""
    sources = {
        os.path.join(project_root, "config.json"): prefix + "_config.json",
        os.path.join(project_root, "build_scene.py"): prefix + "_build_scene.py",
        os.path.join(repository_root, "render_shaft_composite.py"):
            prefix + "_render_shaft_composite.py",
        os.path.join(project_root, "scene_files", "scene_base.pbrt"):
            prefix + "_base.pbrt",
        os.path.join(project_root, "scene_files", "scene_shaft.pbrt"):
            prefix + "_shaft.pbrt",
        os.path.join(repository_root, "docs", "shaft-compositing.md"):
            prefix + "_shaft-compositing.md",
    }
    for source, destination in sources.items():
        shutil.copy2(source, destination)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: render_shaft_composite.py <project-name>")
    repository_root = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(repository_root, sys.argv[1])
    config_path = os.path.join(project_root, "config.json")
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
    prefix = os.path.join(archive, f"{cfg['project']['name']}_{stamp}")
    base_path = prefix + "_base.png"
    shaft_path = prefix + "_shaft.png"
    composite_path = prefix + "_composite.png"

    builder = load_scene_builder(project_root)
    render(builder, configure_base(cfg, shaft_label), project_root,
           pbrt, flags, base_path)
    render(builder, configure_shaft(
               cfg,
               shaft_label,
               float(options.get("surface_reflectance_scale", 0.0)),
               float(options.get("terrain_reflectance_scale", 0.0)),
           ), project_root,
           pbrt, flags, shaft_path)
    composite(base_path, shaft_path, composite_path,
              float(options.get("base_opacity", 1.0)),
              float(options.get("shaft_opacity", 0.65)),
              float(options.get("blur_radius", 1.0)))
    archive_supporting_files(prefix, repository_root, project_root)
    print("Composite complete:", composite_path, flush=True)


if __name__ == "__main__":
    main()
