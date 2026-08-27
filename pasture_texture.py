"""Deterministic seamless pasture texture maps for PBRT terrain."""

from pathlib import Path

import numpy as np
from PIL import Image


def _normalized_field(rng, size, sigma_parallel, sigma_perpendicular, angle):
    """Return periodic anisotropically filtered noise in the range [-1, 1]."""

    noise = rng.standard_normal((size, size))
    spectrum = np.fft.fft2(noise)
    frequency = np.fft.fftfreq(size) * size
    kx, kz = np.meshgrid(frequency, frequency)
    cosine, sine = np.cos(angle), np.sin(angle)
    parallel = kx * cosine + kz * sine
    perpendicular = -kx * sine + kz * cosine
    filter_kernel = np.exp(
        -0.5 * (
            (parallel / sigma_parallel) ** 2
            + (perpendicular / sigma_perpendicular) ** 2
        )
    )
    field = np.fft.ifft2(spectrum * filter_kernel).real
    field -= field.mean()
    percentile = np.percentile(np.abs(field), 99.5)
    return np.clip(field / max(percentile, 1e-9), -1.0, 1.0)


def generate_pasture_maps(config, output_directory):
    """Generate seamless, layered grass-sward albedo and bump maps."""

    size = int(config.get("resolution", 2048))
    if size < 256:
        raise ValueError("pasture texture resolution must be at least 256")
    seed = int(config.get("seed", 97))
    angle = np.radians(float(config.get("flow_direction_degrees", 18.0)))
    rng = np.random.default_rng(seed)

    # Pasture reads as a continuous sward: broad growth variation underneath
    # several dense, mostly aligned blade-frequency bands. A weaker crossing
    # layer prevents the surface from looking combed or artificially striped.
    macro = _normalized_field(rng, size, 5.0, 5.0, 0.0)
    clumps = _normalized_field(rng, size, 16.0, 25.0, angle)
    long_blades = _normalized_field(rng, size, 18.0, 210.0, angle)
    short_blades = _normalized_field(rng, size, 48.0, 390.0, angle + 0.08)
    crossing_blades = _normalized_field(rng, size, 35.0, 260.0, angle - 0.55)
    sward = np.tanh(
        1.35 * (
            0.50 * long_blades
            + 0.35 * short_blades
            + 0.15 * crossing_blades
        )
    )

    low = np.asarray(config.get("dark_color", [46, 91, 25]), dtype=np.float32)
    high = np.asarray(config.get("light_color", [92, 139, 46]), dtype=np.float32)
    broad = np.clip(0.50 + 0.18 * macro + 0.12 * clumps, 0.0, 1.0)
    color = low + broad[..., None] * (high - low)

    fiber_contrast = float(config.get("fiber_contrast", 0.16))
    color *= 1.0 + fiber_contrast * sward[..., None]
    color = np.clip(color, 0.0, 255.0).astype(np.uint8)

    bump_contrast = float(config.get("bump_contrast", 0.16))
    bump = 0.5 + bump_contrast * (0.82 * sward + 0.18 * clumps)
    bump = np.clip(bump * 255.0, 0.0, 255.0).astype(np.uint8)

    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    albedo_path = output_directory / "pasture_albedo.png"
    bump_path = output_directory / "pasture_bump.png"
    Image.fromarray(color, "RGB").save(albedo_path, optimize=True)
    Image.fromarray(bump, "L").save(bump_path, optimize=True)
    return albedo_path, bump_path
