"""Deterministic clustered surface mottling for a distant inhabited vista."""

from pathlib import Path

import numpy as np
from PIL import Image


def _smoothstep(edge0, edge1, values):
    amount = np.clip((values - edge0) / max(edge1 - edge0, 1e-9), 0.0, 1.0)
    return amount * amount * (3.0 - 2.0 * amount)


def _periodic_field(rng, size, feature_size):
    """Return seamless filtered noise with features sized in map fractions."""

    feature_size = max(float(feature_size), 1.0 / size)
    noise = rng.standard_normal((size, size))
    spectrum = np.fft.fft2(noise)
    frequency = np.fft.fftfreq(size) * size
    kx, kz = np.meshgrid(frequency, frequency)
    cutoff = 1.0 / feature_size
    kernel = np.exp(-0.5 * (kx * kx + kz * kz) / (cutoff * cutoff))
    field = np.fft.ifft2(spectrum * kernel).real
    field -= field.mean()
    scale = np.percentile(np.abs(field), 99.5)
    return np.clip(field / max(scale, 1e-9), -1.0, 1.0)


def _linear_to_srgb(values):
    values = np.clip(values, 0.0, 1.0)
    return np.where(
        values <= 0.0031308,
        12.92 * values,
        1.055 * np.power(values, 1.0 / 2.4) - 0.055,
    )


def generate_vista_surface_mottle(config, base_reflectance, output_path):
    """Generate one seamless albedo map suggesting distant habitation."""

    size = int(config.get("resolution", 2048))
    if size < 256:
        raise ValueError("vista surface-mottle resolution must be at least 256")
    seed = int(config.get("seed", 941))
    rng = np.random.default_rng(seed)

    cluster = _periodic_field(rng, size, config.get("cluster_size", 0.20))
    mottle = _periodic_field(rng, size, config.get("mottle_size", 0.012))
    fine = _periodic_field(rng, size, config.get("fine_size", 0.003))

    cluster_floor = np.clip(float(config.get("cluster_floor", 0.0)), 0.0, 1.0)
    cluster_mask = cluster_floor + (1.0 - cluster_floor) * _smoothstep(
        -0.28, 0.34, cluster
    )
    signal = 0.72 * mottle + 0.28 * fine
    coverage = float(config.get("coverage", 0.10))
    softness = max(float(config.get("softness", 0.08)), 1e-6)
    occupied = _smoothstep(coverage - softness, coverage + softness, signal)
    mottle_amount = cluster_mask * occupied

    base = np.asarray(base_reflectance, dtype=np.float32)
    if base.shape != (3,):
        raise ValueError("vista surface-mottle base reflectance requires three values")
    inhabited = np.asarray(
        config.get("mottle_reflectance", [0.18, 0.16, 0.14]),
        dtype=np.float32,
    )
    accent = np.asarray(
        config.get("accent_reflectance", [0.32, 0.23, 0.13]),
        dtype=np.float32,
    )
    if inhabited.shape != (3,) or accent.shape != (3,):
        raise ValueError("vista surface-mottle colors require three values")

    contrast = np.clip(float(config.get("contrast", 0.85)), 0.0, 1.0)
    base_variation = np.clip(1.0 + 0.10 * cluster, 0.88, 1.12)
    color = base[None, None, :] * base_variation[..., None]
    blend = np.clip(contrast * mottle_amount, 0.0, 1.0)
    color = color * (1.0 - blend[..., None]) + inhabited * blend[..., None]

    accent_fraction = np.clip(float(config.get("accent_fraction", 0.06)), 0.0, 1.0)
    candidates = fine[mottle_amount > 0.25]
    if accent_fraction > 0.0 and candidates.size:
        cutoff = np.quantile(candidates, 1.0 - accent_fraction)
        accents = mottle_amount * _smoothstep(cutoff - 0.035, cutoff + 0.035, fine)
        color = color * (1.0 - accents[..., None]) + accent * accents[..., None]

    encoded = np.rint(_linear_to_srgb(color) * 255.0).astype(np.uint8)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(encoded, "RGB").save(output_path, optimize=True)
    return output_path
