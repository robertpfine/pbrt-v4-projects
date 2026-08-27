"""Terrain-aware procedural scatter for ground-cover scene details."""

from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class ScatterPoint:
    position: tuple[float, float, float]
    normal: tuple[float, float, float]
    rotation: float
    scale: float
    aspect: tuple[float, float, float]
    variant: int


def _fade(value):
    return value * value * (3.0 - 2.0 * value)


def _hash(ix, iz, seed):
    value = math.sin(ix * 127.1 + iz * 311.7 + seed * 74.7) * 43758.5453123
    return value - math.floor(value)


def _noise(x, z, seed):
    ix, iz = math.floor(x), math.floor(z)
    tx, tz = _fade(x - ix), _fade(z - iz)
    n00, n10 = _hash(ix, iz, seed), _hash(ix + 1, iz, seed)
    n01, n11 = _hash(ix, iz + 1, seed), _hash(ix + 1, iz + 1, seed)
    nx0 = n00 + (n10 - n00) * tx
    nx1 = n01 + (n11 - n01) * tx
    return nx0 + (nx1 - nx0) * tz


def spatial_direction_offset(x, z, config, seed=1):
    """Return a smooth signed angular offset for a terrain direction field."""

    if not config.get("enabled", False):
        return 0.0
    frequency = float(config.get("frequency", 0.006))
    variation = float(config.get("direction_variation_degrees", 90.0))
    octaves = max(1, int(config.get("octaves", 2)))
    persistence = float(config.get("persistence", 0.45))
    amplitude = 1.0
    total = 0.0
    weight = 0.0
    for octave in range(octaves):
        sample = 2.0 * _noise(
            x * frequency * (2.0 ** octave),
            z * frequency * (2.0 ** octave),
            seed + 193 * octave,
        ) - 1.0
        total += amplitude * sample
        weight += amplitude
        amplitude *= persistence
    normalized = total / max(weight, 1e-9)
    return variation * max(-1.0, min(1.0, normalized))


def scatter_points(terrain, config, seed_offset=0):
    """Return deterministic placements accepted by region, slope, and patch masks."""

    if not config.get("enabled", False):
        return []
    count = int(config.get("count", 0))
    if count <= 0:
        return []
    seed = int(config.get("seed", 1)) + seed_offset
    rng = random.Random(seed)
    region = config.get("region", {})
    center = region.get("center", [0.0, 0.0])
    size = region.get("size", [terrain.width, terrain.depth])
    width = min(float(size[0]), terrain.width)
    depth = min(float(size[1]), terrain.depth)
    max_slope = float(config.get("max_slope_degrees", 90.0))
    scale_range = config.get("scale", [1.0, 1.0])
    patch = config.get("patchiness", {})
    patch_strength = float(patch.get("strength", 0.0))
    patch_frequency = float(patch.get("frequency", 0.02))
    variants = max(1, int(config.get("variants", 1)))
    y_offset = float(config.get("y_offset", 0.02))
    exclusion = config.get("exclusion", {})
    exclusion_center = exclusion.get("center", [0.0, 0.0])
    exclusion_radius = float(exclusion.get("radius", 0.0))
    attraction = config.get("attraction", {})
    attraction_center = attraction.get("center", [0.0, 0.0])
    attraction_radius = float(attraction.get("radius", 0.0))
    attraction_strength = float(attraction.get("strength", 0.0))

    result = []
    attempts = 0
    max_attempts = max(100, count * 80)
    while len(result) < count and attempts < max_attempts:
        attempts += 1
        x = float(center[0]) + rng.uniform(-0.5 * width, 0.5 * width)
        z = float(center[1]) + rng.uniform(-0.5 * depth, 0.5 * depth)
        if not (terrain.x_min <= x <= terrain.x_max
                and terrain.z_min <= z <= terrain.z_max):
            continue
        if exclusion_radius > 0.0:
            distance = math.hypot(x - exclusion_center[0], z - exclusion_center[1])
            if distance < exclusion_radius:
                continue
        acceptance = 1.0
        if patch_strength > 0.0:
            field = _noise(x * patch_frequency, z * patch_frequency, seed + 101)
            acceptance *= (1.0 - patch_strength) + patch_strength * field
        if attraction_radius > 0.0 and attraction_strength > 0.0:
            distance = math.hypot(x - attraction_center[0], z - attraction_center[1])
            proximity = max(0.0, 1.0 - distance / attraction_radius)
            acceptance *= (1.0 - attraction_strength) + attraction_strength * proximity
        if rng.random() > acceptance:
            continue
        sample = terrain.sample(x, z)
        if sample.slope_degrees > max_slope:
            continue
        scale = rng.uniform(float(scale_range[0]), float(scale_range[1]))
        aspect = (
            rng.uniform(0.78, 1.22),
            rng.uniform(0.70, 1.25),
            rng.uniform(0.78, 1.22),
        )
        result.append(ScatterPoint(
            position=(x, sample.height + y_offset, z),
            normal=sample.normal,
            rotation=rng.uniform(0.0, 360.0),
            scale=scale,
            aspect=aspect,
            variant=rng.randrange(variants),
        ))
    return result


def alignment_rotation(normal):
    """Return an axis-angle rotation carrying local +Y to a surface normal."""

    nx, ny, nz = normal
    ny = max(-1.0, min(1.0, ny))
    angle = math.degrees(math.acos(ny))
    axis = (nz, 0.0, -nx)
    length = math.hypot(axis[0], axis[2])
    if length < 1e-9:
        return 0.0, (1.0, 0.0, 0.0)
    return angle, (axis[0] / length, 0.0, axis[2] / length)
