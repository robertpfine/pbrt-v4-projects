#!/usr/bin/env python3
"""Normalize Art Studio cloud configuration for the compiled grid builder."""

from __future__ import annotations

import ctypes.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from cloud_boundary import CloudBoundary, normalized_edge_fades


CONTRACT_VERSION = 1


def _vector3(value: Any, label: str) -> list[float]:
    if isinstance(value, (int, float)):
        return [float(value)] * 3
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} requires one number or three numbers")
    return [float(component) for component in value]


def _merged(shared: dict, local: dict, key: str) -> dict:
    return {**shared.get(key, {}), **local.get(key, {})}


def _native_noise_library() -> str:
    frozen_library = (
        Path(__file__).resolve().parent
        / "render_dependencies"
        / "cloud_perlin.so"
    )
    if frozen_library.is_file():
        return str(frozen_library)
    try:
        import noise._perlin as native_perlin
    except ModuleNotFoundError as error:
        raise RuntimeError("Python noise package is required for cloud-grid parity") from error
    return str(Path(native_perlin.__file__).resolve())


def _python_library() -> str:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    library = ctypes.util.find_library(version)
    if not library:
        raise RuntimeError(f"could not locate the {version} shared library")
    return library


def normalized_cloud_job(cloud_config: dict, formation: dict, index: int = 0) -> dict:
    """Return a self-contained, explicit contract for one legacy cloud entry."""

    name = str(formation.get("name", f"cloud_{index}"))
    center = _vector3(formation.get("center"), f"{name}.center")
    dimensions = _vector3(formation.get("size"), f"{name}.size")
    if any(value <= 0.0 for value in dimensions):
        raise ValueError(f"{name}.size values must be positive")
    resolution = [int(value) for value in formation.get("resolution", [40, 24, 32])]
    if len(resolution) != 3 or any(value < 2 for value in resolution):
        raise ValueError(f"{name}.resolution requires three integers of at least 2")

    generator = str(formation.get("form", "lobed"))
    if generator not in {"lobed", "mottled_veil"}:
        raise ValueError(f"{name}: unsupported cloud generator {generator!r}")

    shape = _merged(cloud_config, formation, "shape")
    noise = _merged(cloud_config, formation, "fractal_noise")
    depth_slope = _merged(cloud_config, formation, "depth_slope")
    depth_profile = _merged(cloud_config, formation, "depth_profile")
    boundary = CloudBoundary(
        formation.get("boundary", {}), center, dimensions, depth_slope, name
    )
    shared_appearance = cloud_config.get("appearance", {})
    local_appearance = formation.get("appearance", {})
    appearance = {**shared_appearance, **local_appearance}
    underside = {
        **shared_appearance.get("underside", {}),
        **local_appearance.get("underside", {}),
    }

    lobes = []
    for lobe_index, lobe in enumerate(formation.get("lobes", [])):
        lobes.append(
            {
                "center_offset": _vector3(
                    lobe.get("center_offset"),
                    f"{name}.lobes[{lobe_index}].center_offset",
                ),
                "radii": _vector3(
                    lobe.get("radii"), f"{name}.lobes[{lobe_index}].radii"
                ),
                "strength": float(lobe.get("strength", 1.0)),
            }
        )
    if generator == "lobed" and not lobes:
        raise ValueError(f"{name}: lobed clouds require at least one lobe")

    return {
        "contract_version": CONTRACT_VERSION,
        "name": name,
        "medium_name": "cloud_{}_{}".format(
            index,
            "".join(character if character.isalnum() or character == "_" else "_"
                    for character in name),
        ),
        "generator": generator,
        "center": center,
        "dimensions": dimensions,
        "boundary": boundary.contract(),
        "resolution": resolution,
        "density_field": {
            "shape": {
                "bottom_fade": float(shape.get("bottom_fade", 80.0)),
                "top_fade": float(shape.get("top_fade", 120.0)),
            },
            "noise": {
                "seed": int(noise.get("seed", 1)),
                "frequency": _vector3(noise.get("frequency", 0.002), "frequency"),
                "octaves": float(noise.get("octaves", 2.0)),
                "roughness": float(noise.get("roughness", 0.5)),
                "frequency_jump": float(noise.get("frequency_jump", 2.0)),
                "coverage": float(noise.get("coverage", 0.10)),
                "softness": float(noise.get("softness", 0.22)),
                "broad_strength": float(noise.get("broad_strength", 1.0)),
                "detail_strength": float(noise.get("detail_strength", 0.35)),
                "detail_frequency_scale": float(
                    noise.get("detail_frequency_scale", 2.7)
                ),
                "edge_fade_fraction": normalized_edge_fades(
                    noise.get("edge_fade_fraction", [0.08, 0.22, 0.25])
                ),
                "edge_influence": float(noise.get("edge_influence", 0.28)),
                "density_contrast": float(noise.get("density_contrast", 0.65)),
                "density_modulation_min": float(
                    noise.get("density_modulation_min", 0.35)
                ),
                "density_modulation_max": float(
                    noise.get("density_modulation_max", 1.35)
                ),
                "envelope_power": float(noise.get("envelope_power", 0.5)),
                "domain_warp": {
                    "enabled": bool(noise.get("domain_warp", {}).get("enabled", True)),
                    "frequency": _vector3(
                        noise.get("domain_warp", {}).get("frequency", 0.0015),
                        "domain_warp.frequency",
                    ),
                    "strength": _vector3(
                        noise.get("domain_warp", {}).get(
                            "strength", [120.0, 80.0, 120.0]
                        ),
                        "domain_warp.strength",
                    ),
                },
            },
            "depth_slope": {
                "enabled": bool(depth_slope.get("enabled", False)),
                "far_y_offset": float(depth_slope.get("far_y_offset", 0.0)),
            },
            "depth_profile": {
                "enabled": bool(depth_profile.get("enabled", False)),
                "full_density_until_z": float(
                    depth_profile.get("full_density_until_z", center[2])
                ),
                "falloff_distance": float(depth_profile.get("falloff_distance", 1.0)),
                "far_density_scale": float(
                    depth_profile.get("far_density_scale", 0.0)
                ),
            },
            "lobes": lobes,
        },
        "medium": {
            "type": "rgbgrid" if underside.get("enabled", False) else "uniformgrid",
            "density_scale": float(appearance.get("density", 1.0)),
            "scattering": _vector3(
                appearance.get("scattering", [0.006, 0.006, 0.006]), "scattering"
            ),
            "absorption": _vector3(
                appearance.get("absorption", [0.00015, 0.00015, 0.00015]),
                "absorption",
            ),
            "anisotropy": float(appearance.get("anisotropy", 0.2)),
            "underside": {
                "enabled": bool(underside.get("enabled", False)),
                "height_fraction": float(underside.get("height_fraction", 0.42)),
                "transition": float(underside.get("transition", 0.20)),
                "scattering_scale": float(underside.get("scattering_scale", 0.40)),
                "absorption_scale": float(underside.get("absorption_scale", 4.0)),
            },
        },
    }


def write_job(job: dict, filename: Path) -> None:
    filename.parent.mkdir(parents=True, exist_ok=True)
    filename.write_text(
        json.dumps(job, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_compiled_builder(
    job_path: Path,
    output_path: Path,
    executable: Path,
    threads: int = 1,
) -> subprocess.CompletedProcess:
    if threads < 0 or threads > 256:
        raise ValueError("cloud-grid thread count must be between 0 and 256")
    command = [
        str(executable),
        "--spec",
        str(job_path),
        "--output",
        str(output_path),
        "--threads",
        str(threads),
        "--python-library",
        _python_library(),
        "--perlin-library",
        _native_noise_library(),
    ]
    return subprocess.run(command, check=True, text=True, capture_output=True)
