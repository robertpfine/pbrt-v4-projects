"""Designed bounded volumetric cloud formations for PBRT-v4 Art Studio."""

from __future__ import annotations

import math

from noise import pnoise3

from cloud_boundary import CloudBoundary, FACE_NAMES, normalized_edge_fades


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def _smoothstep(value):
    value = _clamp(value)
    return value * value * (3.0 - 2.0 * value)


def _frequency3(value):
    if isinstance(value, (list, tuple)):
        if len(value) != 3:
            raise ValueError("fractal noise frequency requires one or three values")
        return tuple(float(component) for component in value)
    scalar = float(value)
    return scalar, scalar, scalar


def _fractal_sum3(x, y, z, seed, octaves, roughness, frequency_jump):
    """Return an unnormalized 3D Perlin sum modeled on TerrainCreator."""

    whole_octaves = max(1, int(octaves))
    fractional_octave = max(0.0, float(octaves) - whole_octaves)
    amplitude = 1.0
    result = 0.0
    for _ in range(whole_octaves):
        result += amplitude * pnoise3(
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
    if fractional_octave:
        result += fractional_octave * amplitude * pnoise3(
            x,
            y,
            z,
            repeatx=4096,
            repeaty=4096,
            repeatz=4096,
            base=seed,
        )
    return result


class CloudFormation:
    """One artist-designed envelope rendered through a uniform density grid."""

    def __init__(self, config, module_config=None):
        module_config = module_config or {}
        self.name = str(config.get("name", "cloud"))
        self.center = tuple(float(v) for v in config["center"])
        self.size = tuple(float(v) for v in config["size"])
        self.depth_slope = {
            **module_config.get("depth_slope", {}),
            **config.get("depth_slope", {}),
        }
        self.resolution = tuple(int(v) for v in config.get("resolution", [40, 24, 32]))
        self.form = str(config.get("form", "lobed"))
        self.lobes = tuple(config.get("lobes", ()))
        self.vertical_profile = {
            **module_config.get("shape", {}),
            **config.get("shape", {}),
        }
        self.fractal_noise = {
            **module_config.get("fractal_noise", {}),
            **config.get("fractal_noise", {}),
        }
        self.edge_fades = normalized_edge_fades(
            self.fractal_noise.get("edge_fade_fraction", [0.08, 0.22, 0.25])
        )
        self.depth_profile = {
            **module_config.get("depth_profile", {}),
            **config.get("depth_profile", {}),
        }
        self.procedural = {
            **module_config.get("procedural", {}),
            **config.get("procedural", {}),
        }
        module_appearance = module_config.get("appearance", {})
        local_appearance = config.get("appearance", {})
        appearance = {**module_appearance, **local_appearance}
        self.underside = {
            **module_appearance.get("underside", {}),
            **local_appearance.get("underside", {}),
        }
        self.optical = {
            "type": appearance.get("type", "uniformgrid"),
            "density_scale": appearance.get("density", 1.0),
            "sigma_s": appearance.get("scattering", [0.006, 0.006, 0.006]),
            "sigma_a": appearance.get("absorption", [0.00015, 0.00015, 0.00015]),
            "g": appearance.get("anisotropy", 0.2),
        }

        if len(self.center) != 3 or len(self.size) != 3:
            raise ValueError(f"{self.name}: cloud center and size require three values")
        if any(value <= 0.0 for value in self.size):
            raise ValueError(f"{self.name}: cloud size values must be positive")
        self.boundary = CloudBoundary(
            config.get("boundary", {}), self.center, self.size,
            self.depth_slope, self.name,
        )
        self.base_bounds_min = self.boundary.base_bounds_min
        self.base_bounds_max = self.boundary.base_bounds_max
        self.bounds_min = self.boundary.bounds_min
        self.bounds_max = self.boundary.bounds_max
        if len(self.resolution) != 3 or any(value < 2 for value in self.resolution):
            raise ValueError(f"{self.name}: cloud resolution values must be at least 2")
        if self.form not in ("lobed", "mottled_veil", "pbrt_cloud"):
            raise ValueError(f"{self.name}: unsupported cloud form {self.form!r}")
        if self.form == "lobed" and not self.lobes:
            raise ValueError(f"{self.name}: cloud requires at least one density lobe")
        if self.form == "pbrt_cloud":
            if self.boundary.mode != "spherical_shell":
                raise ValueError(
                    f"{self.name}: pbrt_cloud requires a spherical_shell boundary"
                )
            if self.optical["type"] != "cloud":
                raise ValueError(
                    f"{self.name}: pbrt_cloud requires medium.type cloud"
                )
            for key in ("density", "wispiness", "frequency"):
                value = self.procedural.get(key)
                if (not isinstance(value, (int, float))
                        or not math.isfinite(value) or value < 0.0):
                    raise ValueError(
                        f"{self.name}: procedural.{key} must be nonnegative"
                    )
        for index, lobe in enumerate(self.lobes):
            center_offset = lobe.get("center_offset", ())
            radii = lobe.get("radii", ())
            if (
                len(center_offset) != 3
                or len(radii) != 3
                or any(float(v) <= 0 for v in radii)
            ):
                raise ValueError(
                    f"{self.name}: lobe {index} requires center_offset and positive radii"
                )
        if self.depth_profile.get("enabled", False):
            full_density_z = float(self.depth_profile["full_density_until_z"])
            falloff_distance = float(self.depth_profile["falloff_distance"])
            far_density_scale = float(
                self.depth_profile.get("far_density_scale", 0.0)
            )
            if falloff_distance <= 0.0:
                raise ValueError(
                    f"{self.name}: depth_profile.falloff_distance must be positive"
                )
            if not 0.0 <= far_density_scale <= 1.0:
                raise ValueError(
                    f"{self.name}: depth_profile.far_density_scale must be "
                    "between 0 and 1"
                )

    def _depth_profile_weight(self, z):
        """Reduce far optical density without truncating the cloud deck."""

        if not self.depth_profile.get("enabled", False):
            return 1.0
        full_density_z = float(self.depth_profile["full_density_until_z"])
        falloff_distance = float(self.depth_profile["falloff_distance"])
        far_density_scale = float(
            self.depth_profile.get("far_density_scale", 0.0)
        )
        distance_beyond_full_density = max(0.0, full_density_z - z)
        return max(
            far_density_scale,
            math.exp(-distance_beyond_full_density / falloff_distance),
        )

    def _depth_slope_offset(self, z):
        """Return the vertical displacement of the deck at world Z."""

        if not self.depth_slope.get("enabled", False):
            return 0.0
        near_z = self.base_bounds_max[2]
        far_z = self.base_bounds_min[2]
        depth_fraction = _clamp((near_z - z) / max(near_z - far_z, 1e-9))
        return depth_fraction * float(self.depth_slope.get("far_y_offset", 0.0))

    def _mottled_veil_density(self, x, y, z):
        """Density for a broad cloud veil that continues beyond the frame."""

        fractal = self.fractal_noise
        local = self.boundary.local_coordinates(x, y, z)
        if self.boundary.mode == "corner_prism" and local is None:
            return 0.0
        if self.boundary.mode == "corner_prism":
            bottom_displacement = (
                self.boundary.bottom_y(x, z) - self.boundary.reference_bottom_y
            )
            reference_y = y - bottom_displacement
        else:
            reference_y = y - self._depth_slope_offset(z)
        frequency = _frequency3(fractal.get("frequency", [0.0006, 0.0014, 0.001]))
        seed = int(fractal.get("seed", 1))
        octaves = float(fractal.get("octaves", 2.0))
        roughness = float(fractal.get("roughness", 0.5))
        frequency_jump = float(fractal.get("frequency_jump", 2.0))
        primary = _fractal_sum3(
            x * frequency[0],
            reference_y * frequency[1],
            z * frequency[2],
            seed,
            octaves,
            roughness,
            frequency_jump,
        )
        detail_scale = float(fractal.get("detail_frequency_scale", 2.7))
        detail = _fractal_sum3(
            x * frequency[0] * detail_scale,
            reference_y * frequency[1] * detail_scale,
            z * frequency[2] * detail_scale,
            seed + 401,
            octaves,
            roughness,
            frequency_jump,
        )
        broad_strength = float(fractal.get("broad_strength", 1.0))
        detail_strength = float(fractal.get("detail_strength", 0.35))
        field = 0.5 + broad_strength * primary + detail_strength * detail
        coverage = float(fractal.get("coverage", 0.50))
        softness = max(float(fractal.get("softness", 0.30)), 1e-6)
        mottle = _smoothstep((field - coverage) / softness)

        edge_weight = 1.0
        if self.boundary.mode == "corner_prism":
            for face in FACE_NAMES:
                fade = self.edge_fades[face]
                if fade > 0.0:
                    edge_weight *= _smoothstep(local[face] / fade)
        else:
            # Preserve legacy XYZ semantics exactly, including zero being
            # clamped to a microscopic fade rather than meaning "no fade".
            for axis, coordinate in enumerate((x, reference_y, z)):
                extent = self.base_bounds_max[axis] - self.base_bounds_min[axis]
                normalized = (coordinate - self.base_bounds_min[axis]) / extent
                names = (("left", "right"), ("bottom", "top"), ("far", "near"))
                for face, distance in zip(names[axis], (normalized, 1.0 - normalized)):
                    fade = max(self.edge_fades[face], 1e-6)
                    edge_weight *= _smoothstep(distance / fade)

        density_scale = float(self.optical.get("density_scale", 1.0))
        depth_weight = self._depth_profile_weight(z)
        return _clamp(
            density_scale * mottle * edge_weight * depth_weight,
            0.0,
            density_scale,
        )

    def _envelope(self, x, y, z):
        union = 0.0
        for lobe in self.lobes:
            center = tuple(
                self.center[axis] + float(lobe["center_offset"][axis])
                for axis in range(3)
            )
            radii = lobe["radii"]
            distance = math.sqrt(sum(
                ((coordinate - float(center[axis])) / float(radii[axis])) ** 2
                for axis, coordinate in enumerate((x, y, z))
            ))
            influence = _smoothstep(1.0 - distance)
            influence *= float(lobe.get("strength", 1.0))
            influence = _clamp(influence)
            union = 1.0 - (1.0 - union) * (1.0 - influence)
        return union

    def density(self, x, y, z):
        if self.form == "mottled_veil":
            return self._mottled_veil_density(x, y, z)

        fractal = self.fractal_noise
        seed = int(fractal.get("seed", 1))
        octaves = float(fractal.get("octaves", 2.0))
        roughness = float(fractal.get("roughness", 0.5))
        frequency_jump = float(fractal.get("frequency_jump", 2.0))

        domain_warp = fractal.get("domain_warp", {})
        if domain_warp.get("enabled", True):
            warp_frequency = _frequency3(domain_warp.get("frequency", 0.0015))
            warp_strength = tuple(float(value) for value in domain_warp.get(
                "strength", [120.0, 80.0, 120.0]
            ))
            if len(warp_strength) != 3:
                raise ValueError(
                    f"{self.name}: fractal_noise.domain_warp.strength requires three values"
                )
            warp_x = _fractal_sum3(
                x * warp_frequency[0],
                y * warp_frequency[1],
                z * warp_frequency[2],
                seed + 101,
                octaves,
                roughness,
                frequency_jump,
            )
            warp_y = _fractal_sum3(
                x * warp_frequency[0],
                y * warp_frequency[1],
                z * warp_frequency[2],
                seed + 211,
                octaves,
                roughness,
                frequency_jump,
            )
            warped_x = x + warp_strength[0] * warp_x
            warped_y = y + warp_strength[1] * warp_y
            warped_z = z + warp_strength[2] * (0.55 * warp_x - 0.45 * warp_y)
        else:
            warped_x, warped_y, warped_z = x, y, z

        envelope = self._envelope(warped_x, warped_y, warped_z)
        if envelope <= 0.0:
            return 0.0

        bottom_fade = float(self.vertical_profile.get("bottom_fade", 80.0))
        top_fade = float(self.vertical_profile.get("top_fade", 120.0))
        if self.boundary.mode == "corner_prism":
            local = self.boundary.local_coordinates(x, y, z)
            if local is None:
                return 0.0
            bottom_y = self.boundary.bottom_y(x, z)
            top_y = bottom_y + self.boundary.thickness
        else:
            bottom_y, top_y = self.bounds_min[1], self.bounds_max[1]
        bottom = _smoothstep((y - bottom_y) / max(bottom_fade, 1e-9))
        top = _smoothstep((top_y - y) / max(top_fade, 1e-9))

        frequency = _frequency3(fractal.get("frequency", 0.002))
        density_noise = _fractal_sum3(
            warped_x * frequency[0],
            warped_y * frequency[1],
            warped_z * frequency[2],
            seed + 307,
            octaves,
            roughness,
            frequency_jump,
        )

        # Noise deforms and breaks up the cloud edge, but a strong designed
        # envelope cannot be excavated into the large holes seen in render
        # 014351.  The third independent fractal field also varies density
        # continuously inside the occupied volume.
        coverage = float(fractal.get("coverage", 0.10))
        edge_influence = float(fractal.get("edge_influence", 0.28))
        softness = max(float(fractal.get("softness", 0.22)), 1e-6)
        support = _smoothstep(
            (envelope + edge_influence * density_noise - coverage) / softness
        )
        density_contrast = float(fractal.get("density_contrast", 0.65))
        modulation_min = float(fractal.get("density_modulation_min", 0.35))
        modulation_max = float(fractal.get("density_modulation_max", 1.35))
        modulation = _clamp(
            1.0 + density_contrast * density_noise,
            modulation_min,
            modulation_max,
        )
        envelope_power = max(float(fractal.get("envelope_power", 0.5)), 1e-6)
        density_scale = float(self.optical.get("density_scale", 1.0))
        density = (
            density_scale
            * support
            * envelope ** envelope_power
            * modulation
            * bottom
            * top
        )
        return _clamp(density, 0.0, density_scale)

    def optical_coefficients(self, density, y, z=None, x=None):
        """Return spatial absorption and scattering for one cloud sample."""

        sigma_a = tuple(float(value) for value in self.optical["sigma_a"])
        sigma_s = tuple(float(value) for value in self.optical["sigma_s"])
        if not self.underside.get("enabled", False):
            return (
                tuple(density * value for value in sigma_a),
                tuple(density * value for value in sigma_s),
            )

        height_fraction = float(self.underside.get("height_fraction", 0.42))
        transition = max(float(self.underside.get("transition", 0.20)), 1e-6)
        if self.boundary.mode == "corner_prism" and x is not None and z is not None:
            normalized_y = (
                (y - self.boundary.bottom_y(x, z)) / self.boundary.thickness
            )
        else:
            reference_y = y - self._depth_slope_offset(z) if z is not None else y
            normalized_y = (
                (reference_y - self.base_bounds_min[1])
                / max(self.base_bounds_max[1] - self.base_bounds_min[1], 1e-9)
            )
        transition_start = height_fraction - 0.5 * transition
        underside_weight = 1.0 - _smoothstep(
            (normalized_y - transition_start) / transition
        )
        scattering_scale = float(
            self.underside.get("scattering_scale", 0.40)
        )
        absorption_scale = float(
            self.underside.get("absorption_scale", 4.0)
        )
        scattering_factor = 1.0 + underside_weight * (scattering_scale - 1.0)
        absorption_factor = 1.0 + underside_weight * (absorption_scale - 1.0)
        return (
            tuple(density * absorption_factor * value for value in sigma_a),
            tuple(density * scattering_factor * value for value in sigma_s),
        )

    def optical_grids(self):
        """Return flattened RGB grids for a height-dependent cloud medium."""

        nx, ny, nz = self.resolution
        density = self.density_grid()
        sigma_a_grid = []
        sigma_s_grid = []
        offset = 0
        for iz in range(nz):
            z = self.bounds_min[2] + (
                (self.bounds_max[2] - self.bounds_min[2]) * iz / (nz - 1)
            )
            for iy in range(ny):
                y = self.bounds_min[1] + (
                    (self.bounds_max[1] - self.bounds_min[1]) * iy / (ny - 1)
                )
                for ix in range(nx):
                    x = self.bounds_min[0] + (
                        (self.bounds_max[0] - self.bounds_min[0]) * ix / (nx - 1)
                    )
                    sigma_a, sigma_s = self.optical_coefficients(
                        density[offset], y, z, x
                    )
                    sigma_a_grid.extend(sigma_a)
                    sigma_s_grid.extend(sigma_s)
                    offset += 1
        return sigma_a_grid, sigma_s_grid

    def density_grid(self):
        nx, ny, nz = self.resolution
        result = []
        for iz in range(nz):
            z = self.bounds_min[2] + (self.bounds_max[2] - self.bounds_min[2]) * iz / (nz - 1)
            for iy in range(ny):
                y = self.bounds_min[1] + (self.bounds_max[1] - self.bounds_min[1]) * iy / (ny - 1)
                for ix in range(nx):
                    x = self.bounds_min[0] + (self.bounds_max[0] - self.bounds_min[0]) * ix / (nx - 1)
                    result.append(self.density(x, y, z))
        return result


def create_clouds(config):
    """Return enabled cloud formations from the sky.clouds module."""

    if not config or not config.get("enabled", False):
        return []
    formations = config.get("formations", [])
    if not isinstance(formations, list):
        raise ValueError("sky.clouds.formations must be an array")
    return [
        CloudFormation(item, config)
        for item in formations
        if item.get("enabled", True)
    ]


def configured_cloud_module(sky):
    """Adapt self-contained sky clouds to the established cloud generator."""

    formations = []
    for cloud in sky.get("clouds", []):
        density = cloud.get("density_field", {})
        medium = cloud.get("medium", {})
        formations.append({
            "name": cloud.get("name", "cloud"),
            "enabled": cloud.get("enabled", False),
            "center": cloud.get("placement", {}).get("position", [0, 0, 0]),
            "size": cloud.get("dimensions", []),
            "boundary": cloud.get("boundary", {}),
            "resolution": density.get("resolution", []),
            "form": density.get("generator", "lobed"),
            "shape": density.get("shape", {}),
            "fractal_noise": density.get("noise", {}),
            "depth_slope": density.get("depth_slope", {}),
            "depth_profile": density.get("depth_profile", {}),
            "procedural": density.get("procedural", {}),
            "lobes": density.get("lobes", []),
            "appearance": {
                "type": medium.get("type", "uniformgrid"),
                "density": medium.get("density_scale", 1.0),
                "scattering": medium.get("scattering", [0.006] * 3),
                "absorption": medium.get("absorption", [0.00015] * 3),
                "anisotropy": medium.get("anisotropy", 0.2),
                "underside": medium.get("underside", {}),
            },
        })
    return {
        "enabled": True,
        "grid_builder": sky.get("cloud_grid_builder", {}),
        "formations": formations,
    }
