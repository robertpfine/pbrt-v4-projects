"""Planar phyllotaxis generators based on Vogel's sunflower model.

The model follows Figure 4.1 of *The Algorithmic Beauty of Plants*:

    phi_n = n * alpha
    r_n = c * sqrt(n)

Angles are supplied in degrees.  The generated points lie in the XZ plane,
with Y reserved for an optional supporting-surface height function.
"""

from dataclasses import dataclass
import math
from typing import Callable, Iterable, Optional


@dataclass(frozen=True)
class PhyllotaxisPoint:
    """One organ placement in a phyllotactic pattern."""

    index: int
    angle_degrees: float
    radius: float
    x: float
    y: float
    z: float


HeightFunction = Callable[[int, float, float], float]


def vogel_points(
    count: int,
    divergence_angle: float = 137.5,
    spacing: float = 1.0,
    center: Iterable[float] = (0.0, 0.0, 0.0),
    height_function: Optional[HeightFunction] = None,
) -> list[PhyllotaxisPoint]:
    """Return ``count`` organ positions using Vogel's planar formula.

    ``height_function``, when supplied, receives ``(index, radius,
    normalized_radius)`` and returns a local Y offset.  Omitting it produces
    the strictly planar Figure 4.1 construction.
    """

    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    if not math.isfinite(divergence_angle):
        raise ValueError("divergence_angle must be finite")
    if not math.isfinite(spacing) or spacing <= 0:
        raise ValueError("spacing must be a positive finite number")

    center_values = tuple(float(value) for value in center)
    if len(center_values) != 3 or not all(math.isfinite(v) for v in center_values):
        raise ValueError("center must contain three finite coordinates")
    cx, cy, cz = center_values

    max_radius = spacing * math.sqrt(max(1, count - 1))
    points = []
    for index in range(count):
        angle_degrees = index * divergence_angle
        angle_radians = math.radians(angle_degrees)
        radius = spacing * math.sqrt(index)
        normalized_radius = radius / max_radius
        local_y = 0.0
        if height_function is not None:
            local_y = float(height_function(index, radius, normalized_radius))
            if not math.isfinite(local_y):
                raise ValueError("height_function must return finite values")

        points.append(
            PhyllotaxisPoint(
                index=index,
                angle_degrees=angle_degrees,
                radius=radius,
                x=cx + radius * math.cos(angle_radians),
                y=cy + local_y,
                z=cz + radius * math.sin(angle_radians),
            )
        )

    return points


def dome_height(height: float) -> HeightFunction:
    """Return a hemispheroid-like height function for later 3D heads."""

    if not math.isfinite(height):
        raise ValueError("height must be finite")

    def evaluate(_index: int, _radius: float, normalized_radius: float) -> float:
        radial_term = max(0.0, 1.0 - normalized_radius * normalized_radius)
        return height * math.sqrt(radial_term)

    return evaluate
