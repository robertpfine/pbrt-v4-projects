"""Deterministic equal-area environment maps for PBRT-v4 skies."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _smoothstep(edge0, edge1, values):
    width = max(float(edge1) - float(edge0), 1e-9)
    amount = np.clip((values - edge0) / width, 0.0, 1.0)
    return amount * amount * (3.0 - 2.0 * amount)


def _equal_area_square_to_sphere(width, height):
    """Return directions at texel centers using PBRT's exact square mapping."""

    u = 2.0 * ((np.arange(width, dtype=np.float32) + 0.5) / width) - 1.0
    v = 2.0 * ((np.arange(height, dtype=np.float32) + 0.5) / height) - 1.0
    u, v = np.meshgrid(u, v)
    up, vp = np.abs(u), np.abs(v)
    signed_distance = 1.0 - (up + vp)
    radius = 1.0 - np.abs(signed_distance)
    phi = np.where(
        radius == 0.0,
        1.0,
        (vp - up) / np.maximum(radius, 1e-20) + 1.0,
    ) * (np.pi / 4.0)
    z = np.copysign(1.0 - radius * radius, signed_distance)
    radial = radius * np.sqrt(np.maximum(0.0, 2.0 - radius * radius))
    x = np.copysign(np.cos(phi), u) * radial
    y = np.copysign(np.sin(phi), v) * radial
    return x, y, z


def _directional_field(rng, directions, feature_fraction, wave_count):
    """Evaluate seamless band-limited noise as a function of sphere direction."""

    x, y, z = directions
    center_frequency = 1.0 / max(float(feature_fraction), 1e-4)
    field = np.zeros_like(x, dtype=np.float32)
    weight_sum = 0.0
    for _ in range(wave_count):
        axis = rng.normal(size=3)
        axis /= np.linalg.norm(axis)
        frequency = center_frequency * rng.uniform(0.72, 1.38)
        phase = rng.uniform(0.0, 2.0 * np.pi)
        weight = rng.uniform(0.65, 1.0)
        argument = frequency * (
            axis[0] * x + axis[1] * y + axis[2] * z
        ) + phase
        field += weight * np.sin(argument).astype(np.float32)
        weight_sum += weight * weight
    field /= np.sqrt(max(weight_sum / 2.0, 1e-9))
    field -= np.mean(field)
    scale = np.percentile(np.abs(field), 99.5)
    return np.clip(field / max(float(scale), 1e-9), -1.0, 1.0)


def _linear_to_srgb(values):
    values = np.clip(values, 0.0, 1.0)
    return np.where(
        values <= 0.0031308,
        12.92 * values,
        1.055 * np.power(values, 1.0 / 2.4) - 0.055,
    )


def _rgb(config, name, default):
    value = np.asarray(config.get(name, default), dtype=np.float32)
    if value.shape != (3,) or not np.all(np.isfinite(value)):
        raise ValueError(f"sky background environment.{name} requires 3 finite values")
    if np.any(value < 0):
        raise ValueError(f"sky background environment.{name} cannot be negative")
    return value


def _resolution(config):
    resolution = config.get("resolution", [2048, 2048])
    if (
        not isinstance(resolution, list)
        or len(resolution) != 2
        or any(not isinstance(v, int) or isinstance(v, bool) for v in resolution)
    ):
        raise ValueError("sky background environment.resolution requires 2 integers")
    width, height = resolution
    if width < 512 or height < 512 or width != height:
        raise ValueError(
            "sky background environment.resolution must be a square map of at least 512x512"
        )
    return width, height


def generate_overcast_equal_area(config):
    """Generate a seamless linear-RGB overcast field in PBRT equal-area space."""

    width, height = _resolution(config)
    directions = _equal_area_square_to_sphere(width, height)
    rng = np.random.default_rng(int(config.get("seed", 823)))
    broad = _directional_field(
        rng, directions, config.get("broad_feature_fraction", 0.18), 10
    )
    medium = _directional_field(
        rng, directions, config.get("medium_feature_fraction", 0.065), 14
    )
    detail = _directional_field(
        rng, directions, config.get("detail_feature_fraction", 0.022), 18
    )

    # World Y is vertical. Equal-area texels represent equal solid angles, so
    # an ordinary image mean is also the spherical mean.
    altitude = directions[1]
    horizon_weight = np.power(np.clip(1.0 - np.abs(altitude), 0.0, 1.0), 1.5)
    signal = 0.62 * broad + 0.29 * medium + 0.09 * detail
    signal += float(config.get("horizon_bias", 0.24)) * horizon_weight

    coverage = float(config.get("coverage", 0.88))
    softness = float(config.get("softness", 0.16))
    if not 0.0 <= coverage <= 1.0:
        raise ValueError("sky background environment.coverage must be within [0, 1]")
    if softness <= 0.0:
        raise ValueError("sky background environment.softness must be positive")
    threshold = float(np.quantile(signal, 1.0 - coverage))
    cloud = _smoothstep(threshold - softness, threshold + softness, signal)

    contrast = float(config.get("contrast", 0.52))
    if contrast < 0.0:
        raise ValueError("sky background environment.contrast cannot be negative")
    modeled_tone = np.clip(
        0.50 + contrast * (0.70 * broad + 0.22 * medium + 0.08 * detail),
        0.0,
        1.0,
    )
    clear = _rgb(config, "clear_color", [0.50, 0.57, 0.66])
    dark = _rgb(config, "cloud_dark_color", [0.34, 0.37, 0.41])
    light = _rgb(config, "cloud_light_color", [0.76, 0.78, 0.80])
    target = _rgb(config, "target_average_color", [0.62, 0.68, 0.75])

    cloud_color = dark + modeled_tone[..., None] * (light - dark)
    color = clear + cloud[..., None] * (cloud_color - clear)
    mean = np.mean(color, axis=(0, 1))
    color *= (target / np.maximum(mean, 1e-9))[None, None, :]
    return np.clip(color, 0.0, 1.0).astype(np.float32)


def _write_pfm(path, color):
    """Write little-endian linear RGB in PBRT's supported PFM format."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    height, width, channels = color.shape
    if channels != 3:
        raise ValueError("PFM output requires RGB pixels")
    with path.open("wb") as output:
        output.write(f"PF\n{width} {height}\n-1.0\n".encode("ascii"))
        np.flipud(color).astype("<f4", copy=False).tofile(output)
    return path


def generate_twilight_equal_area(config):
    """Artist-controlled horizon glow and blue upper sky, with world Y up.

    This smooth environment supplies fill and reflections; the separate sun
    and volumetric clouds supply directional light and cloud shapes.
    """
    width, height = _resolution(config)
    directions = _equal_area_square_to_sphere(width, height)
    altitude = directions[1]
    zenith = _rgb(config, "zenith_color", [0.10, 0.18, 0.34])
    horizon = _rgb(config, "horizon_color", [0.35, 0.24, 0.23])
    nadir = _rgb(config, "nadir_color", [0.10, 0.12, 0.17])
    degrees = config.get("horizon_transition_degrees", 35.0)
    if (isinstance(degrees, bool) or not isinstance(degrees, (int, float))
            or not np.isfinite(degrees) or not 0 < degrees <= 90):
        raise ValueError("sky background environment.horizon_transition_degrees "
                         "must be within (0, 90]")
    blend = _smoothstep(0.0, np.sin(np.radians(degrees)), np.abs(altitude))
    pole = np.where((altitude >= 0)[..., None], zenith, nadir)
    color = (horizon + blend[..., None] * (pole - horizon)).astype(np.float32)
    count = config.get("star_count", 0)
    radius = config.get("star_radius_degrees", 0.08)
    brightness = config.get("star_brightness", 8.0)
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 2000:
        raise ValueError("sky background environment.star_count must be an integer within [0, 2000]")
    for name, value, upper in (("star_radius_degrees", radius, 1.0),
                               ("star_brightness", brightness, float("inf"))):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not np.isfinite(value) or not 0 < value <= upper):
            raise ValueError(f"sky background environment.{name} must be positive "
                             f"and no greater than {upper}")
    # Seeded directions give consistent stars across map resolutions. Angular
    # Gaussian points cross map seams continuously and fade into horizon glow.
    rng = np.random.default_rng(int(config.get("seed", 823)))
    variance = np.radians(radius) ** 2
    star_light = np.zeros_like(altitude)
    for _ in range(count):
        star_y = rng.uniform(np.sin(np.radians(8.0)), 1.0)
        azimuth = rng.uniform(0.0, 2.0 * np.pi)
        radial = np.sqrt(1.0 - star_y * star_y)
        dot = (directions[0] * radial * np.cos(azimuth)
               + altitude * star_y
               + directions[2] * radial * np.sin(azimuth))
        glow = np.exp(-np.maximum(0.0, 1.0 - dot) / variance)
        fade = _smoothstep(0.0, np.sin(np.radians(25.0)), star_y)
        star_light += glow * brightness * rng.uniform(0.35, 1.0) * fade
    color += star_light[..., None] * np.array([0.85, 0.90, 1.0], dtype=np.float32)
    return color


def generate_twilight_environment(config, output_directory):
    """Write a reproducible twilight map using the existing PBRT mapping."""
    color = generate_twilight_equal_area(config)
    output_directory = Path(output_directory)
    path = _write_pfm(output_directory / "twilight_environment.pfm", color)
    encoded = np.rint(_linear_to_srgb(color) * 255.0).astype(np.uint8)
    Image.fromarray(encoded, "RGB").save(
        output_directory / "twilight_environment_equalarea.png", optimize=True
    )
    return path


def generate_overcast_environment(config, output_directory):
    """Generate PBRT equal-area PFM plus a human-viewable map preview."""

    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    color = generate_overcast_equal_area(config)
    environment_path = output_directory / "overcast_environment.pfm"
    preview_path = output_directory / "overcast_environment_equalarea.png"
    _write_pfm(environment_path, color)
    encoded = np.rint(_linear_to_srgb(color) * 255.0).astype(np.uint8)
    Image.fromarray(encoded, "RGB").save(preview_path, optimize=True)
    return environment_path
