"""Deterministic procedural terrain surfaces and PBRT mesh data."""

from dataclasses import dataclass
import math


def validate_basin(basin):
    """Validate an optional, world-space depression in a terrain heightfield."""
    if not isinstance(basin, dict):
        return ["basin must be an object"]
    errors = []
    if not isinstance(basin.get("enabled", False), bool):
        errors.append("basin.enabled must be boolean")

    def finite(value):
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value))

    for key, default in (("center", [0.0, 0.0]), ("radii", [100.0, 100.0])):
        value = basin.get(key, default)
        if (not isinstance(value, (list, tuple)) or len(value) != 2
                or not all(finite(v) for v in value)):
            errors.append(f"basin.{key} must contain two finite numbers")
        elif key == "radii" and any(v <= 0 for v in value):
            errors.append("basin.radii must be positive")
    if not finite(basin.get("floor_height", -10.0)):
        errors.append("basin.floor_height must be finite")
    for key, default, low, high in (
        ("inner_fraction", 0.5, 0.0, 1.0),
        ("shore_variation", 0.0, 0.0, 0.3),
    ):
        value = basin.get(key, default)
        if not finite(value) or not low <= value < high:
            errors.append(f"basin.{key} must be in [{low}, {high})")
    return errors


@dataclass(frozen=True)
class TerrainSample:
    height: float
    normal: tuple[float, float, float]
    slope_degrees: float


class RollingHillside:
    """An inclined plane enriched with smooth multi-octave value noise."""

    def __init__(self, config):
        size = config.get("size", [300.0, 300.0])
        resolution = config.get("resolution", [129, 129])
        if isinstance(resolution, int):
            resolution = [resolution, resolution]
        self.width, self.depth = (float(size[0]), float(size[1]))
        center = config.get("center", [0.0, 0.0])
        self.center_x, self.center_z = (float(center[0]), float(center[1]))
        self.x_min = self.center_x - 0.5 * self.width
        self.x_max = self.center_x + 0.5 * self.width
        self.z_min = self.center_z - 0.5 * self.depth
        self.z_max = self.center_z + 0.5 * self.depth
        self.nx, self.nz = (int(resolution[0]), int(resolution[1]))
        self.base_height = float(config.get("base_height", 0.0))
        slope = config.get("slope", {})
        self.slope_angle = math.radians(float(slope.get("direction_degrees", 0.0)))
        self.grade = float(slope.get("grade", 0.0))
        leveling = slope.get("foreground_leveling", {})
        self.foreground_leveling = bool(leveling.get("enabled", False))
        self.leveling_angle = math.radians(
            float(leveling.get("direction_degrees", 0.0))
        )
        self.leveling_start = float(leveling.get("start", 0.0))
        self.leveling_end = float(leveling.get("end", 1.0))
        self.minimum_grade_ratio = float(leveling.get("minimum_grade_ratio", 0.0))
        target_height = leveling.get("target_height")
        self.leveling_target_height = (
            None if target_height is None else float(target_height)
        )
        noise = config.get("noise", {})
        self.seed = int(noise.get("seed", 1))
        self.amplitude = float(noise.get("amplitude", 0.0))
        self.frequency = float(noise.get("frequency", 0.01))
        self.octaves = int(noise.get("octaves", 3))
        self.persistence = float(noise.get("persistence", 0.5))
        self.lacunarity = float(noise.get("lacunarity", 2.0))
        right_profile = config.get("right_profile", {})
        self.right_profile_enabled = bool(right_profile.get("enabled", False))
        self.right_profile_angle = math.radians(
            float(right_profile.get("direction_degrees", 322.0))
        )
        self.right_dip_center = float(right_profile.get("dip_center", 220.0))
        self.right_dip_width = float(right_profile.get("dip_width", 150.0))
        self.right_dip_depth = float(right_profile.get("dip_depth", 70.0))
        self.right_rise_center = float(right_profile.get("rise_center", 600.0))
        self.right_rise_width = float(right_profile.get("rise_width", 250.0))
        self.right_rise_height = float(right_profile.get("rise_height", 55.0))
        basin = config.get("basin", {})
        errors = validate_basin(basin)
        if errors:
            raise ValueError("; ".join(errors))
        self.basin_enabled = basin.get("enabled", False)
        self.basin_center = basin.get("center", [0.0, 0.0])
        self.basin_radii = basin.get("radii", [100.0, 100.0])
        self.basin_floor = basin.get("floor_height", -10.0)
        self.basin_inner = basin.get("inner_fraction", 0.5)
        self.basin_variation = basin.get("shore_variation", 0.0)
        if self.width <= 0 or self.depth <= 0:
            raise ValueError("terrain size values must be positive")
        if self.nx < 2 or self.nz < 2:
            raise ValueError("terrain resolution values must be at least 2")
        if self.octaves < 1:
            raise ValueError("terrain noise octaves must be at least 1")
        if self.foreground_leveling and self.leveling_end <= self.leveling_start:
            raise ValueError("terrain foreground leveling end must exceed start")
        if not 0.0 <= self.minimum_grade_ratio <= 1.0:
            raise ValueError("terrain minimum grade ratio must be between 0 and 1")
        if self.right_dip_width <= 0.0 or self.right_rise_width <= 0.0:
            raise ValueError("right dip/rise widths must be positive")

    def _right_profile(self, distance):
        dip = -self.right_dip_depth * math.exp(
            -0.5 * ((distance - self.right_dip_center) / self.right_dip_width) ** 2
        )
        rise = self.right_rise_height * math.exp(
            -0.5 * ((distance - self.right_rise_center) / self.right_rise_width) ** 2
        )
        return dip + rise

    @staticmethod
    def _fade(value):
        return value * value * value * (value * (value * 6.0 - 15.0) + 10.0)

    def _lattice(self, ix, iz):
        value = math.sin(
            ix * 127.1 + iz * 311.7 + self.seed * 74.7
        ) * 43758.5453123
        return 2.0 * (value - math.floor(value)) - 1.0

    def _value_noise(self, x, z):
        ix, iz = math.floor(x), math.floor(z)
        tx, tz = x - ix, z - iz
        sx, sz = self._fade(tx), self._fade(tz)
        n00 = self._lattice(ix, iz)
        n10 = self._lattice(ix + 1, iz)
        n01 = self._lattice(ix, iz + 1)
        n11 = self._lattice(ix + 1, iz + 1)
        nx0 = n00 + (n10 - n00) * sx
        nx1 = n01 + (n11 - n01) * sx
        return nx0 + (nx1 - nx0) * sz

    def height(self, x, z):
        along_slope = x * math.cos(self.slope_angle) + z * math.sin(self.slope_angle)
        planar_height = self.grade * along_slope
        if self.foreground_leveling:
            direction_x = math.cos(self.leveling_angle)
            direction_z = math.sin(self.leveling_angle)
            foreground_distance = x * direction_x + z * direction_z
            transition = (
                (foreground_distance - self.leveling_start)
                / (self.leveling_end - self.leveling_start)
            )
            transition = max(0.0, min(1.0, transition))
            transition = transition * transition * (3.0 - 2.0 * transition)

            anchor_distance = max(0.0, foreground_distance - self.leveling_start)
            anchor_x = x - anchor_distance * direction_x
            anchor_z = z - anchor_distance * direction_z
            anchor_along_slope = (
                anchor_x * math.cos(self.slope_angle)
                + anchor_z * math.sin(self.slope_angle)
            )
            level_height = self.grade * anchor_along_slope
            if self.leveling_target_height is not None:
                level_height = self.leveling_target_height
            residual_height = level_height + self.minimum_grade_ratio * (
                planar_height - level_height
            )
            planar_height += transition * (residual_height - planar_height)

        result = self.base_height + planar_height
        amplitude = self.amplitude
        frequency = self.frequency
        for _ in range(self.octaves):
            result += amplitude * self._value_noise(x * frequency, z * frequency)
            amplitude *= self.persistence
            frequency *= self.lacunarity
        if self.right_profile_enabled:
            distance = (
                x * math.cos(self.right_profile_angle)
                + z * math.sin(self.right_profile_angle)
            )
            # Preserve the established tree elevation at the profile origin.
            result += self._right_profile(distance) - self._right_profile(0.0)
        if self.basin_enabled:
            bx = (x - self.basin_center[0]) / self.basin_radii[0]
            bz = (z - self.basin_center[1]) / self.basin_radii[1]
            angle = math.atan2(bz, bx)
            rim = 1.0 + self.basin_variation * (
                0.6 * math.sin(3.0 * angle) + 0.4 * math.cos(5.0 * angle)
            )
            radius = math.hypot(bx, bz) / rim
            blend = self._fade(max(0.0, min(
                1.0, (radius - self.basin_inner) / (1.0 - self.basin_inner)
            )))
            # Only excavate: a basin must never raise pre-existing low ground.
            floor = min(result, self.basin_floor)
            result = floor + blend * (result - floor)
        return result

    def sample(self, x, z):
        epsilon = min(self.width / (self.nx - 1), self.depth / (self.nz - 1)) * 0.25
        dhdx = (self.height(x + epsilon, z) - self.height(x - epsilon, z)) / (2.0 * epsilon)
        dhdz = (self.height(x, z + epsilon) - self.height(x, z - epsilon)) / (2.0 * epsilon)
        normal = (-dhdx, 1.0, -dhdz)
        magnitude = math.sqrt(sum(component * component for component in normal))
        normal = tuple(component / magnitude for component in normal)
        slope = math.degrees(math.atan(math.sqrt(dhdx * dhdx + dhdz * dhdz)))
        return TerrainSample(self.height(x, z), normal, slope)

    def mesh(self):
        points = []
        normals = []
        for iz in range(self.nz):
            z = self.z_min + self.depth * iz / (self.nz - 1)
            for ix in range(self.nx):
                x = self.x_min + self.width * ix / (self.nx - 1)
                sample = self.sample(x, z)
                points.append((x, sample.height, z))
                normals.append(sample.normal)
        indices = []
        for iz in range(self.nz - 1):
            for ix in range(self.nx - 1):
                lower = iz * self.nx + ix
                upper = lower + self.nx
                indices.extend((lower, upper, lower + 1, lower + 1, upper, upper + 1))
        return points, normals, indices


def create_terrain(config):
    """Create one enabled terrain-heightfield landform implementation."""

    if not config.get("enabled", False):
        return None
    topography = config.get("topography", {})
    if not topography.get("enabled", False):
        return None
    if topography.get("generator") != "terrain_heightfield":
        raise ValueError(
            f"unsupported topography generator: {topography.get('generator')!r}"
        )

    patches = config.get("geometry", {}).get("patches", [])
    plane_patches = [
        patch
        for patch in patches
        if patch.get("enabled", False) and patch.get("generator") == "plane"
    ]
    if len(plane_patches) != 1:
        raise ValueError(
            "terrain_heightfield requires exactly one enabled plane patch"
        )
    patch = plane_patches[0]
    placement = config.get("placement", {})
    position = placement.get("position", [0.0, 0.0, 0.0])
    local_position = patch.get("local_position", [0.0, 0.0, 0.0])
    rotations = (
        placement.get("rotation_degrees", [0.0, 0.0, 0.0]),
        patch.get("local_rotation_degrees", [0.0, 0.0, 0.0]),
    )
    if any(any(float(value) != 0.0 for value in rotation) for rotation in rotations):
        raise ValueError(
            "terrain_heightfield does not yet support nonzero landform rotations"
        )

    parameters = topography.get("parameters", {})
    terrain_config = {
        "size": patch.get("dimensions", [300.0, 300.0]),
        "resolution": patch.get("subdivisions", [129, 129]),
        "center": [
            float(position[0]) + float(local_position[0]),
            float(position[2]) + float(local_position[2]),
        ],
        "base_height": float(position[1]) + float(local_position[1]),
        "slope": parameters.get("slope", {}),
        "noise": parameters.get("noise", {}),
        "right_profile": parameters.get("right_profile", {}),
        "basin": parameters.get("basin", {}),
    }
    return RollingHillside(terrain_config)
