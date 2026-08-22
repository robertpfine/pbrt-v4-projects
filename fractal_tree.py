"""Recursive geometric fractal trees with explicit scaling laws."""

from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class Segment:
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    radius0: float
    radius1: float
    kind: str


def _normalize(vector):
    length = math.sqrt(sum(component * component for component in vector))
    return tuple(component / max(1e-9, length) for component in vector)


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def fractal_tree(config):
    """Generate an asymmetric recursive tree with conserved branch area.

    At every fork, child radii satisfy r1**alpha + r2**alpha = rp**alpha.
    Recursion stops by physical radius rather than by a fixed generation count,
    leaving length, angle, and azimuth variation free to shape the silhouette.
    """

    seed = int(config.get("seed", 23))
    rng = random.Random(seed)
    trunk_height = float(config.get("trunk_height", 42.0))
    trunk_segments = int(config.get("trunk_segments", 6))
    base_radius = float(config.get("base_radius", 5.5))
    crown_radius = float(config.get("crown_radius", base_radius * 0.72))
    initial_length = float(config.get("initial_length", 34.0))
    alpha = float(config.get("alpha", 2.2))
    min_radius = float(config.get("min_radius", base_radius * 0.10))
    dominant_length_ratio = float(config.get("dominant_length_ratio", 0.76))
    lateral_length_ratio = float(config.get("lateral_length_ratio", 0.62))
    dominant_angle = math.radians(float(config.get("dominant_angle", 24.0)))
    lateral_angle = math.radians(float(config.get("lateral_angle", 48.0)))
    upward_bias = float(config.get("upward_bias", 0.18))
    angle_jitter = math.radians(float(config.get("angle_jitter", 12.0)))
    length_jitter = float(config.get("length_jitter", 0.10))
    asymmetry_min = float(config.get("asymmetry_min", 1.05))
    asymmetry_max = float(config.get("asymmetry_max", 1.55))
    max_depth = int(config.get("max_depth", 12))
    leaves_enabled = bool(config.get("leaves_enabled", True))
    leaf_length = float(config.get("leaf_length", 2.8))
    leaf_width = float(config.get("leaf_width", 0.72))
    crownlet_depth = int(config.get("crownlet_depth", 3))
    crownlet_length = float(config.get("crownlet_length", 5.5))
    crownlet_length_ratio = float(config.get("crownlet_length_ratio", 0.62))
    crownlet_angle = math.radians(float(config.get("crownlet_angle", 38.0)))
    crownlet_radius_ratio = float(config.get("crownlet_radius_ratio", 0.46))
    leaves_per_tip = int(config.get("leaves_per_tip", 5))
    segments = []

    previous = (0.0, 0.0, 0.0)
    for index in range(1, trunk_segments + 1):
        t = index / trunk_segments
        current = (
            0.45 * math.sin(t * 2.4),
            trunk_height * t,
            0.30 * math.sin(t * 3.1 + 0.5),
        )
        r0 = base_radius + (crown_radius - base_radius) * ((index - 1) / trunk_segments)
        r1 = base_radius + (crown_radius - base_radius) * t
        segments.append(Segment(previous, current, r0, r1, "wood"))
        previous = current

    def basis(direction):
        reference = (0.0, 1.0, 0.0)
        if abs(sum(direction[i] * reference[i] for i in range(3))) > 0.92:
            reference = (1.0, 0.0, 0.0)
        side = _normalize(_cross(direction, reference))
        normal = _normalize(_cross(side, direction))
        return side, normal

    def tilted(direction, azimuth, angle):
        side, normal = basis(direction)
        radial = tuple(
            math.cos(azimuth) * side[i] + math.sin(azimuth) * normal[i]
            for i in range(3)
        )
        value = tuple(
            math.cos(angle) * direction[i] + math.sin(angle) * radial[i]
            + (upward_bias if i == 1 else 0.0)
            for i in range(3)
        )
        return _normalize(value)

    def add_leaf_cluster(point, direction):
        if not leaves_enabled:
            return
        side, normal = basis(direction)
        for leaf_index in range(leaves_per_tip):
            azimuth = (
                2.0 * math.pi * leaf_index / leaves_per_tip
                + rng.uniform(-0.25, 0.25)
            )
            leaf_direction = _normalize(tuple(
                0.42 * direction[i]
                + math.cos(azimuth) * side[i]
                + math.sin(azimuth) * normal[i]
                + (0.22 if i == 1 else 0.0)
                for i in range(3)
            ))
            end = tuple(point[i] + leaf_length * leaf_direction[i] for i in range(3))
            segments.append(Segment(point, end, leaf_width, 0.0, "leaf"))

    def add_crownlet(start, direction, length, radius, depth, phase):
        """Insert fine recursive shoots between a structural tip and leaves."""

        end = tuple(start[i] + direction[i] * length for i in range(3))
        tip_radius = max(radius * crownlet_radius_ratio, 0.035)
        segments.append(Segment(start, end, radius, tip_radius, "foliage"))
        if depth >= crownlet_depth:
            add_leaf_cluster(end, direction)
            return

        spread = crownlet_angle * (1.0 - 0.10 * depth)
        jitter = rng.uniform(-0.18, 0.18)
        child_length = length * crownlet_length_ratio
        add_crownlet(
            end,
            tilted(direction, phase + jitter, spread),
            child_length * rng.uniform(0.90, 1.08),
            tip_radius,
            depth + 1,
            phase + math.radians(137.5),
        )
        add_crownlet(
            end,
            tilted(direction, phase + math.pi - jitter, spread * 1.12),
            child_length * rng.uniform(0.82, 1.02),
            tip_radius * 0.88,
            depth + 1,
            phase - math.radians(99.5),
        )

    def grow(start, direction, length, radius, depth, phase):
        end = tuple(start[i] + direction[i] * length for i in range(3))
        if radius <= min_radius or depth >= max_depth:
            segments.append(Segment(start, end, radius, max(radius * 0.55, 0.04), "foliage"))
            add_crownlet(
                end,
                direction,
                crownlet_length * rng.uniform(0.82, 1.12),
                max(radius * 0.55, 0.04),
                0,
                phase,
            )
            return

        ratio = rng.uniform(asymmetry_min, asymmetry_max)
        smaller = radius / ((ratio ** alpha + 1.0) ** (1.0 / alpha))
        larger = ratio * smaller
        segments.append(Segment(start, end, radius, max(larger, smaller), "wood"))

        azimuth = phase + rng.uniform(-0.28, 0.28)
        dominant_direction = tilted(
            direction, azimuth,
            dominant_angle + rng.uniform(-angle_jitter, angle_jitter),
        )
        lateral_direction = tilted(
            direction, azimuth + math.pi,
            lateral_angle + rng.uniform(-angle_jitter, angle_jitter),
        )
        grow(
            end, dominant_direction,
            length * dominant_length_ratio * (1.0 + rng.uniform(-length_jitter, length_jitter)),
            larger, depth + 1, phase + math.radians(137.5),
        )
        grow(
            end, lateral_direction,
            length * lateral_length_ratio * (1.0 + rng.uniform(-length_jitter, length_jitter)),
            smaller, depth + 1, phase - math.radians(99.5),
        )

    leader_specs = ((18.0, 0.98), (143.0, 0.88), (258.0, 0.80))
    for degrees, vigor in leader_specs:
        azimuth = math.radians(degrees)
        direction = _normalize((0.58 * math.cos(azimuth), 0.62, 0.58 * math.sin(azimuth)))
        grow(previous, direction, initial_length * vigor, crown_radius * vigor, 0, azimuth)
    return segments
