"""Bounded volumetric rain curtains for PBRT-v4 Art Studio."""

from __future__ import annotations

import math

from noise import pnoise3


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def _smoothstep(value):
    value = _clamp(value)
    return value * value * (3.0 - 2.0 * value)


def _vector3(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} requires three values")
    return tuple(float(component) for component in value)


def _fractal_sum3(x, y, z, seed, octaves, roughness, frequency_jump):
    amplitude = 1.0
    value = 0.0
    for _ in range(max(1, int(octaves))):
        value += amplitude * pnoise3(
            x,
            y,
            z,
            repeatx=4096,
            repeaty=4096,
            repeatz=4096,
            base=seed,
        )
        x *= frequency_jump
        y *= frequency_jump
        z *= frequency_jump
        amplitude *= roughness
    return value


class RainCurtain:
    """One finite rain shaft with vertically coherent heterogeneous density."""

    def __init__(self, config, module_config=None):
        module_config = module_config or {}
        self.name = str(config.get("name", "rain_curtain"))
        self.center = _vector3(config.get("center"), f"{self.name}: center")
        self.size = _vector3(config.get("size"), f"{self.name}: size")
        self.resolution = tuple(
            int(value) for value in config.get("resolution", [64, 48, 24])
        )
        self.bounds_min = tuple(
            self.center[axis] - 0.5 * self.size[axis] for axis in range(3)
        )
        self.bounds_max = tuple(
            self.center[axis] + 0.5 * self.size[axis] for axis in range(3)
        )
        self.pattern = {**module_config.get("pattern", {}), **config.get("pattern", {})}
        appearance = {**module_config.get("appearance", {}), **config.get("appearance", {})}
        self.optical = {
            "density_scale": float(appearance.get("density", 1.0)),
            "sigma_s": _vector3(
                appearance.get("scattering", [0.0005, 0.0006, 0.0007]),
                f"{self.name}: scattering",
            ),
            "sigma_a": _vector3(
                appearance.get("absorption", [0.00008, 0.00007, 0.00006]),
                f"{self.name}: absorption",
            ),
            "g": float(appearance.get("anisotropy", 0.35)),
        }

        if any(value <= 0.0 for value in self.size):
            raise ValueError(f"{self.name}: rain-curtain size values must be positive")
        if len(self.resolution) != 3 or any(value < 2 for value in self.resolution):
            raise ValueError(
                f"{self.name}: rain-curtain resolution values must be at least 2"
            )
        if self.optical["density_scale"] < 0.0:
            raise ValueError(f"{self.name}: rain density must be nonnegative")
        if not -1.0 < self.optical["g"] < 1.0:
            raise ValueError(f"{self.name}: rain anisotropy must be between -1 and 1")

    def _edge_weight(self, x, y, z):
        fractions = _vector3(
            self.pattern.get("edge_fade_fraction", [0.12, 0.10, 0.30]),
            f"{self.name}: edge_fade_fraction",
        )
        weight = 1.0
        for axis, coordinate in enumerate((x, y, z)):
            extent = self.size[axis]
            normalized = (coordinate - self.bounds_min[axis]) / extent
            fade = max(fractions[axis], 1e-6)
            weight *= _smoothstep(normalized / fade)
            weight *= _smoothstep((1.0 - normalized) / fade)
        return weight

    def density(self, x, y, z):
        pattern = self.pattern
        seed = int(pattern.get("seed", 751))
        octaves = int(pattern.get("octaves", 3))
        roughness = float(pattern.get("roughness", 0.5))
        frequency_jump = float(pattern.get("frequency_jump", 2.0))

        wind_tilt = math.tan(math.radians(float(pattern.get("wind_tilt_degrees", 0.0))))
        wind_direction = math.radians(float(pattern.get("wind_direction_degrees", 0.0)))
        fall_distance = y - self.bounds_min[1]
        sample_x = x + fall_distance * wind_tilt * math.cos(wind_direction)
        sample_z = z + fall_distance * wind_tilt * math.sin(wind_direction)

        broad_frequency = _vector3(
            pattern.get("broad_frequency", [0.0015, 0.00035, 0.0020]),
            f"{self.name}: broad_frequency",
        )
        streak_frequency = _vector3(
            pattern.get("streak_frequency", [0.030, 0.00045, 0.006]),
            f"{self.name}: streak_frequency",
        )
        broad = _fractal_sum3(
            sample_x * broad_frequency[0],
            y * broad_frequency[1],
            sample_z * broad_frequency[2],
            seed,
            octaves,
            roughness,
            frequency_jump,
        )
        streak = _fractal_sum3(
            sample_x * streak_frequency[0],
            y * streak_frequency[1],
            sample_z * streak_frequency[2],
            seed + 313,
            max(1, octaves - 1),
            roughness,
            frequency_jump,
        )
        detail = pnoise3(
            sample_x * streak_frequency[0] * 2.3,
            y * streak_frequency[1] * 0.7,
            sample_z * streak_frequency[2] * 1.7,
            repeatx=4096,
            repeaty=4096,
            repeatz=4096,
            base=seed + 719,
        )

        signal = 0.5 + 0.72 * streak + 0.28 * detail
        coverage = float(pattern.get("coverage", 0.46))
        softness = max(float(pattern.get("softness", 0.16)), 1e-6)
        streak_mask = _smoothstep((signal - coverage) / softness)
        base_density = float(pattern.get("base_density", 0.24))
        contrast = float(pattern.get("contrast", 0.85))
        sheet_weight = _clamp(base_density + contrast * broad)
        density_scale = self.optical["density_scale"]
        return density_scale * streak_mask * sheet_weight * self._edge_weight(x, y, z)

    def density_grid(self):
        nx, ny, nz = self.resolution
        density = []
        for iz in range(nz):
            z = self.bounds_min[2] + self.size[2] * iz / (nz - 1)
            for iy in range(ny):
                y = self.bounds_min[1] + self.size[1] * iy / (ny - 1)
                for ix in range(nx):
                    x = self.bounds_min[0] + self.size[0] * ix / (nx - 1)
                    density.append(self.density(x, y, z))
        return density


def create_rain_curtains(config):
    """Return enabled rain curtains from the normalized writer contract."""

    if not config or not config.get("enabled", False):
        return []
    curtains = config.get("curtains", [])
    if not isinstance(curtains, list):
        raise ValueError("rain.curtains must be an array")
    return [
        RainCurtain(item, config)
        for item in curtains
        if item.get("enabled", True)
    ]
