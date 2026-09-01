"""Designed, deterministic terrain bands for distant landscape horizons.

The ridge silhouette is built from explicit peaks.  Perlin noise is applied
only as subordinate surface irregularity, so setting its amplitude to zero
still produces a complete, intentional hill form.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable

from terrain_details import ScatterPoint


@dataclass(frozen=True)
class HillSample:
    height: float
    normal: tuple[float, float, float]


@dataclass(frozen=True)
class HorizonTree:
    position: tuple[float, float, float]
    height: float
    crown_radius: float
    variant: int
    form: str


class DistantHillLayer:
    """One world-space terrain band with front, ridge, and rear slopes."""

    _GRADIENTS = (
        (1.0, 0.0),
        (-1.0, 0.0),
        (0.0, 1.0),
        (0.0, -1.0),
        (0.7071067811865476, 0.7071067811865476),
        (-0.7071067811865476, 0.7071067811865476),
        (0.7071067811865476, -0.7071067811865476),
        (-0.7071067811865476, -0.7071067811865476),
    )

    def __init__(self, config: dict):
        self.name = str(config.get("name", "hill_layer"))
        center = config.get("center", [0.0, 0.0])
        size = config.get("size", [1000.0, 300.0])
        resolution = config.get("resolution", [129, 25])
        self.center_x, self.center_z = float(center[0]), float(center[1])
        self.width, self.depth = float(size[0]), float(size[1])
        self.nx, self.nz = int(resolution[0]), int(resolution[1])
        self.rotation = math.radians(float(config.get("rotation_degrees", 0.0)))
        self.base_elevation = float(config.get("base_elevation", 0.0))
        self.ridge_base_height = float(config.get("ridge_base_height", 50.0))
        self.peaks = tuple(config.get("peaks", ()))
        self.ridge_profile = tuple(config.get("ridge_profile", ()))
        self.reflectance = tuple(
            float(value)
            for value in config.get("material", {}).get(
                "reflectance", [0.12, 0.16, 0.09]
            )
        )
        self.shading_normal_up_blend = float(
            config.get("shading_normal_up_blend", 0.0)
        )

        cross_section = config.get("cross_section", {})
        self.ridge_position = float(cross_section.get("ridge_position", 0.45))
        self.front_power = float(cross_section.get("front_power", 1.0))
        self.back_power = float(cross_section.get("back_power", 1.0))

        noise = config.get("noise", {})
        self.seed = int(noise.get("seed", 1))
        self.noise_amplitude = float(noise.get("amplitude", 0.0))
        self.noise_frequency = float(noise.get("frequency", 0.01))
        self.noise_octaves = int(noise.get("octaves", 3))
        self.noise_persistence = float(noise.get("persistence", 0.5))
        self.noise_lacunarity = float(noise.get("lacunarity", 2.0))

        if self.width <= 0.0 or self.depth <= 0.0:
            raise ValueError(f"{self.name}: hill size values must be positive")
        if self.nx < 2 or self.nz < 2:
            raise ValueError(f"{self.name}: hill resolution values must be at least 2")
        if not 0.0 < self.ridge_position < 1.0:
            raise ValueError(f"{self.name}: ridge_position must be between 0 and 1")
        if self.front_power <= 0.0 or self.back_power <= 0.0:
            raise ValueError(f"{self.name}: cross-section powers must be positive")
        if self.ridge_base_height < 0.0:
            raise ValueError(f"{self.name}: ridge_base_height cannot be negative")
        if self.noise_amplitude < 0.0 or self.noise_frequency < 0.0:
            raise ValueError(f"{self.name}: noise amplitude/frequency cannot be negative")
        if self.noise_octaves < 1:
            raise ValueError(f"{self.name}: noise octaves must be at least 1")
        if not 0.0 < self.noise_persistence <= 1.0:
            raise ValueError(f"{self.name}: noise persistence must be in (0, 1]")
        if self.noise_lacunarity < 1.0:
            raise ValueError(f"{self.name}: noise lacunarity must be at least 1")
        if len(self.reflectance) != 3:
            raise ValueError(f"{self.name}: reflectance must contain three values")
        if not 0.0 <= self.shading_normal_up_blend <= 1.0:
            raise ValueError(
                f"{self.name}: shading_normal_up_blend must be in [0, 1]"
            )
        for index, peak in enumerate(self.peaks):
            width = float(peak.get("width", 0.0))
            asymmetry = float(peak.get("asymmetry", 0.0))
            if width <= 0.0:
                raise ValueError(f"{self.name}: peak {index} width must be positive")
            if not -0.95 <= asymmetry <= 0.95:
                raise ValueError(
                    f"{self.name}: peak {index} asymmetry must be in [-0.95, 0.95]"
                )
        previous_position = None
        for index, control in enumerate(self.ridge_profile):
            position = float(control.get("position", 0.0))
            height = float(control.get("height", -1.0))
            if not -1.0 <= position <= 1.0:
                raise ValueError(
                    f"{self.name}: ridge profile position {index} must be in [-1, 1]"
                )
            if height < 0.0:
                raise ValueError(
                    f"{self.name}: ridge profile height {index} cannot be negative"
                )
            if previous_position is not None and position <= previous_position:
                raise ValueError(
                    f"{self.name}: ridge profile positions must strictly ascend"
                )
            previous_position = position
        if self.ridge_profile and len(self.ridge_profile) < 2:
            raise ValueError(f"{self.name}: ridge profile requires at least two points")

    @staticmethod
    def _fade(value: float) -> float:
        return value * value * value * (value * (value * 6.0 - 15.0) + 10.0)

    def _gradient(self, ix: int, iz: int) -> tuple[float, float]:
        # Integer hashing avoids Python's randomized hash and keeps scenes stable.
        value = ix * 0x1F123BB5 ^ iz * 0x05491333 ^ self.seed * 0x6C8E9CF5
        value ^= value >> 16
        value *= 0x7FEB352D
        value ^= value >> 15
        return self._GRADIENTS[value & 7]

    def _perlin(self, x: float, z: float) -> float:
        ix, iz = math.floor(x), math.floor(z)
        tx, tz = x - ix, z - iz

        def dot(gx: int, gz: int, dx: float, dz: float) -> float:
            gradient = self._gradient(gx, gz)
            return gradient[0] * dx + gradient[1] * dz

        n00 = dot(ix, iz, tx, tz)
        n10 = dot(ix + 1, iz, tx - 1.0, tz)
        n01 = dot(ix, iz + 1, tx, tz - 1.0)
        n11 = dot(ix + 1, iz + 1, tx - 1.0, tz - 1.0)
        sx, sz = self._fade(tx), self._fade(tz)
        nx0 = n00 + (n10 - n00) * sx
        nx1 = n01 + (n11 - n01) * sx
        return nx0 + (nx1 - nx0) * sz

    def _fbm(self, local_x: float, local_z: float) -> float:
        if self.noise_amplitude == 0.0 or self.noise_frequency == 0.0:
            return 0.0
        frequency = self.noise_frequency
        weight = 1.0
        total = 0.0
        weight_sum = 0.0
        for _ in range(self.noise_octaves):
            total += weight * self._perlin(local_x * frequency, local_z * frequency)
            weight_sum += weight
            weight *= self.noise_persistence
            frequency *= self.noise_lacunarity
        return self.noise_amplitude * total / max(weight_sum, 1e-12)

    def ridge_height(self, normalized_x: float) -> float:
        """Return designed ridge relief at normalized lateral position [-1, 1]."""

        if self.ridge_profile:
            value = max(-1.0, min(1.0, normalized_x))
            first = self.ridge_profile[0]
            if value <= float(first["position"]):
                return float(first["height"])
            for left, right in zip(self.ridge_profile, self.ridge_profile[1:]):
                left_position = float(left["position"])
                right_position = float(right["position"])
                if value <= right_position:
                    amount = (value - left_position) / (
                        right_position - left_position
                    )
                    # Zero slope at every authored control point creates a
                    # soft painted ridge without Gaussian overlap flattening it.
                    amount = amount * amount * (3.0 - 2.0 * amount)
                    return float(left["height"]) + amount * (
                        float(right["height"]) - float(left["height"])
                    )
            return float(self.ridge_profile[-1]["height"])

        height = self.ridge_base_height
        for peak in self.peaks:
            position = float(peak.get("position", 0.0))
            peak_height = float(peak.get("height", 0.0))
            width = float(peak.get("width", 0.25))
            asymmetry = float(peak.get("asymmetry", 0.0))
            delta = normalized_x - position
            side_width = width * (
                1.0 + asymmetry if delta < 0.0 else 1.0 - asymmetry
            )
            height += peak_height * math.exp(-0.5 * (delta / side_width) ** 2)
        return max(0.0, height)

    def cross_section(self, normalized_depth: float) -> float:
        """Return 0 at both band edges and 1 along the designed ridge."""

        value = max(0.0, min(1.0, normalized_depth))
        if value <= self.ridge_position:
            ramp = value / self.ridge_position
            return self._fade(ramp) ** self.front_power
        ramp = (1.0 - value) / (1.0 - self.ridge_position)
        return self._fade(ramp) ** self.back_power

    def height_local(self, local_x: float, local_z: float) -> float:
        normalized_x = 2.0 * local_x / self.width
        normalized_depth = local_z / self.depth + 0.5
        envelope = self.cross_section(normalized_depth)
        relief = self.ridge_height(normalized_x)
        irregularity = self._fbm(local_x, local_z)
        return self.base_elevation + envelope * (relief + irregularity)

    def local_to_world(self, local_x: float, local_z: float) -> tuple[float, float]:
        cosine, sine = math.cos(self.rotation), math.sin(self.rotation)
        return (
            self.center_x + local_x * cosine + local_z * sine,
            self.center_z - local_x * sine + local_z * cosine,
        )

    def sample_local(self, local_x: float, local_z: float) -> HillSample:
        step = 0.25 * min(
            self.width / (self.nx - 1), self.depth / (self.nz - 1)
        )
        dhdx = (
            self.height_local(local_x + step, local_z)
            - self.height_local(local_x - step, local_z)
        ) / (2.0 * step)
        dhdz = (
            self.height_local(local_x, local_z + step)
            - self.height_local(local_x, local_z - step)
        ) / (2.0 * step)
        local_normal = (-dhdx, 1.0, -dhdz)
        cosine, sine = math.cos(self.rotation), math.sin(self.rotation)
        world_normal = (
            local_normal[0] * cosine + local_normal[2] * sine,
            local_normal[1],
            -local_normal[0] * sine + local_normal[2] * cosine,
        )
        magnitude = math.sqrt(sum(value * value for value in world_normal))
        return HillSample(
            self.height_local(local_x, local_z),
            tuple(value / magnitude for value in world_normal),
        )

    def mesh(self):
        points = []
        normals = []
        for iz in range(self.nz):
            local_z = -0.5 * self.depth + self.depth * iz / (self.nz - 1)
            for ix in range(self.nx):
                local_x = -0.5 * self.width + self.width * ix / (self.nx - 1)
                sample = self.sample_local(local_x, local_z)
                world_x, world_z = self.local_to_world(local_x, local_z)
                points.append((world_x, sample.height, world_z))
                if self.shading_normal_up_blend > 0.0:
                    keep = 1.0 - self.shading_normal_up_blend
                    blended = (
                        keep * sample.normal[0],
                        keep * sample.normal[1] + self.shading_normal_up_blend,
                        keep * sample.normal[2],
                    )
                    magnitude = math.sqrt(sum(value * value for value in blended))
                    normals.append(tuple(value / magnitude for value in blended))
                else:
                    normals.append(sample.normal)
        indices = []
        for iz in range(self.nz - 1):
            for ix in range(self.nx - 1):
                lower = iz * self.nx + ix
                upper = lower + self.nx
                indices.extend((lower, upper, lower + 1, lower + 1, upper, upper + 1))
        return points, normals, indices


def create_distant_hills(config: dict) -> list[DistantHillLayer]:
    """Create enabled distant-hill layers from the module configuration."""

    if not config.get("enabled", False):
        return []
    layers = config.get("layers", [])
    if not isinstance(layers, list):
        raise ValueError("distant_hills.layers must be an array")
    return [DistantHillLayer(layer) for layer in layers if layer.get("enabled", False)]


def create_distant_hill_scatter(
    hill: DistantHillLayer,
    config: dict,
) -> list[ScatterPoint]:
    """Scatter one configured detail population over a distant hill surface."""

    if not config.get("enabled", False):
        return []
    count = int(config.get("count", 0))
    if count < 0:
        raise ValueError("distant detail count cannot be negative")
    if count == 0:
        return []
    lateral_range = config.get("lateral_range", [-1.0, 1.0])
    depth_range = config.get("depth_range", [0.0, 1.0])
    scale_range = config.get("scale", [1.0, 1.0])
    for label, values in (
        ("lateral_range", lateral_range),
        ("depth_range", depth_range),
        ("scale", scale_range),
    ):
        if len(values) != 2 or float(values[0]) > float(values[1]):
            raise ValueError(f"distant detail {label} must be an ascending pair")
    if not (-1.0 <= float(lateral_range[0]) <= float(lateral_range[1]) <= 1.0):
        raise ValueError("distant detail lateral_range must remain in [-1, 1]")
    if not (0.0 <= float(depth_range[0]) <= float(depth_range[1]) <= 1.0):
        raise ValueError("distant detail depth_range must remain in [0, 1]")
    if float(scale_range[0]) <= 0.0:
        raise ValueError("distant detail scale must be positive")

    seed = int(config.get("seed", 1))
    rng = random.Random(seed)
    variants = max(1, int(config.get("variants", 1)))
    max_slope = float(config.get("max_slope_degrees", 90.0))
    y_offset = float(config.get("y_offset", 0.04))
    patch = config.get("patchiness", {})
    patch_strength = max(0.0, min(1.0, float(patch.get("strength", 0.0))))
    patch_frequency = float(patch.get("frequency", 0.01))
    ridge_fade = config.get("ridge_fade", {})
    fade_enabled = bool(ridge_fade.get("enabled", False))
    fade_start = float(ridge_fade.get("start", depth_range[1]))
    fade_end = float(ridge_fade.get("end", depth_range[1]))
    fade_minimum = float(ridge_fade.get("minimum_density", 0.0))
    if fade_enabled:
        if not (
            float(depth_range[0]) <= fade_start < fade_end <= float(depth_range[1])
        ):
            raise ValueError(
                "distant detail ridge_fade must be ascending and inside depth_range"
            )
        if not 0.0 <= fade_minimum <= 1.0:
            raise ValueError(
                "distant detail ridge_fade minimum_density must remain in [0, 1]"
            )
    result = []
    attempts = 0
    max_attempts = max(100, count * 40)
    while len(result) < count and attempts < max_attempts:
        attempts += 1
        normalized_x = rng.uniform(
            float(lateral_range[0]), float(lateral_range[1])
        )
        normalized_depth = rng.uniform(
            float(depth_range[0]), float(depth_range[1])
        )
        if fade_enabled and normalized_depth > fade_start:
            fade_t = min(1.0, (normalized_depth - fade_start) / (fade_end - fade_start))
            smooth_fade = fade_t * fade_t * (3.0 - 2.0 * fade_t)
            acceptance = 1.0 - smooth_fade * (1.0 - fade_minimum)
            if rng.random() > acceptance:
                continue
        local_x = 0.5 * hill.width * normalized_x
        local_z = hill.depth * (normalized_depth - 0.5)
        if patch_strength > 0.0:
            field = 0.5 + hill._perlin(
                local_x * patch_frequency,
                local_z * patch_frequency,
            )
            acceptance = (1.0 - patch_strength) + patch_strength * max(
                0.0, min(1.0, field)
            )
            if rng.random() > acceptance:
                continue
        sample = hill.sample_local(local_x, local_z)
        slope = math.degrees(math.acos(max(-1.0, min(1.0, sample.normal[1]))))
        if slope > max_slope:
            continue
        world_x, world_z = hill.local_to_world(local_x, local_z)
        result.append(ScatterPoint(
            position=(world_x, sample.height + y_offset, world_z),
            normal=sample.normal,
            rotation=rng.uniform(0.0, 360.0),
            scale=rng.uniform(float(scale_range[0]), float(scale_range[1])),
            aspect=(
                rng.uniform(0.82, 1.18),
                rng.uniform(0.78, 1.18),
                rng.uniform(0.82, 1.18),
            ),
            variant=rng.randrange(variants),
        ))
    if len(result) < count:
        raise ValueError(
            f"distant detail accepted only {len(result)} of {count} instances"
        )
    return result


def create_distant_hill_grass(
    hill: DistantHillLayer,
    config: dict,
) -> list[ScatterPoint]:
    """Backward-compatible grass-specific name for distant-hill scattering."""

    return create_distant_hill_scatter(hill, config)


def create_horizon_tree_line(
    config: dict,
    hills: Iterable[DistantHillLayer] | None = None,
) -> list[HorizonTree]:
    """Place a sparse, clustered tree-line silhouette behind a named ridge."""

    tree_line = config.get("tree_line", {})
    if not config.get("enabled", False) or not tree_line.get("enabled", False):
        return []
    available = list(hills) if hills is not None else create_distant_hills(config)
    layer_name = str(tree_line.get("layer", ""))
    layer = next((hill for hill in available if hill.name == layer_name), None)
    if layer is None:
        raise ValueError(
            f"distant_hills.tree_line references inactive layer {layer_name!r}"
        )

    count = int(tree_line.get("count", 0))
    lateral_range = tree_line.get("lateral_range", [-1.0, 1.0])
    height_range = tree_line.get("height", [5.0, 20.0])
    radius_range = tree_line.get("crown_radius", [1.5, 5.0])
    evergreen_height_range = tree_line.get("evergreen_height", height_range)
    evergreen_radius_range = tree_line.get("evergreen_crown_radius", radius_range)
    evergreen_fraction = float(tree_line.get("evergreen_fraction", 0.0))
    cluster_count = int(tree_line.get("cluster_count", 1))
    cluster_spread = float(tree_line.get("cluster_spread", 0.1))
    clustered_fraction = float(tree_line.get("clustered_fraction", 0.82))
    depth_offset = float(tree_line.get("ridge_depth_offset", 0.0))
    depth_jitter = float(tree_line.get("depth_jitter", 0.0))
    variants = tree_line.get("reflectance_variants", [[0.08, 0.10, 0.08]])
    if count < 0:
        raise ValueError("distant_hills.tree_line.count cannot be negative")
    if (
        len(lateral_range) != 2
        or float(lateral_range[0]) >= float(lateral_range[1])
    ):
        raise ValueError("distant_hills.tree_line.lateral_range must ascend")
    if len(height_range) != 2 or not 0.0 < float(height_range[0]) <= float(height_range[1]):
        raise ValueError("distant_hills.tree_line.height must be a positive ascending pair")
    if len(radius_range) != 2 or not 0.0 < float(radius_range[0]) <= float(radius_range[1]):
        raise ValueError(
            "distant_hills.tree_line.crown_radius must be a positive ascending pair"
        )
    if (
        len(evergreen_height_range) != 2
        or not 0.0 < float(evergreen_height_range[0]) <= float(evergreen_height_range[1])
    ):
        raise ValueError(
            "distant_hills.tree_line.evergreen_height must be a positive ascending pair"
        )
    if (
        len(evergreen_radius_range) != 2
        or not 0.0 < float(evergreen_radius_range[0]) <= float(evergreen_radius_range[1])
    ):
        raise ValueError(
            "distant_hills.tree_line.evergreen_crown_radius must be a positive ascending pair"
        )
    if not 0.0 <= evergreen_fraction <= 1.0:
        raise ValueError("distant_hills.tree_line.evergreen_fraction must be in [0, 1]")
    if not 0.0 <= clustered_fraction <= 1.0:
        raise ValueError("distant_hills.tree_line.clustered_fraction must be in [0, 1]")
    if cluster_count < 1 or cluster_spread <= 0.0:
        raise ValueError("distant_hills.tree_line clustering values must be positive")
    if not variants:
        raise ValueError("distant_hills.tree_line requires reflectance variants")

    rng = random.Random(int(tree_line.get("seed", 1)))
    lateral_min, lateral_max = map(float, lateral_range)
    cluster_centers = [
        rng.uniform(lateral_min, lateral_max) for _ in range(cluster_count)
    ]
    ridge_z = layer.depth * (layer.ridge_position - 0.5)
    trees = []
    for _ in range(count):
        if rng.random() < clustered_fraction:
            center = rng.choice(cluster_centers)
            normalized_x = center
            for _attempt in range(8):
                candidate = rng.gauss(center, cluster_spread)
                if lateral_min <= candidate <= lateral_max:
                    normalized_x = candidate
                    break
        else:
            normalized_x = rng.uniform(lateral_min, lateral_max)
        local_x = 0.5 * layer.width * normalized_x
        local_z = ridge_z + depth_offset + rng.uniform(-depth_jitter, depth_jitter)
        world_x, world_z = layer.local_to_world(local_x, local_z)
        base_height = layer.height_local(local_x, local_z)
        form = "evergreen" if rng.random() < evergreen_fraction else "deciduous"
        selected_height_range = (
            evergreen_height_range if form == "evergreen" else height_range
        )
        selected_radius_range = (
            evergreen_radius_range if form == "evergreen" else radius_range
        )
        trees.append(HorizonTree(
            position=(world_x, base_height, world_z),
            height=rng.uniform(
                float(selected_height_range[0]), float(selected_height_range[1])
            ),
            crown_radius=rng.uniform(
                float(selected_radius_range[0]), float(selected_radius_range[1])
            ),
            variant=rng.randrange(len(variants)),
            form=form,
        ))
    return trees


def flatten_triplets(values: Iterable[tuple[float, float, float]]) -> str:
    return " ".join(
        f"{x:.9f} {y:.9f} {z:.9f}" for x, y, z in values
    )
