"""Geometry and face-fade rules for bounded cloud media."""

from __future__ import annotations

import math


CORNER_NAMES = ("near_left", "near_right", "far_right", "far_left")
FACE_NAMES = ("left", "right", "bottom", "top", "near", "far")


def _cross2(origin, end, point):
    """Return the signed XZ-plane cross product for an oriented edge."""

    return ((end[0] - origin[0]) * (point[2] - origin[2])
            - (end[2] - origin[2]) * (point[0] - origin[0]))


def normalized_edge_fades(value):
    """Return six explicit face fades, accepting the legacy XYZ triple."""

    if isinstance(value, (list, tuple)):
        if len(value) != 3:
            raise ValueError(
                "fractal_noise.edge_fade_fraction requires three values"
            )
        x_fade, y_fade, z_fade = (float(component) for component in value)
        result = {
            "left": x_fade,
            "right": x_fade,
            "bottom": y_fade,
            "top": y_fade,
            "near": z_fade,
            "far": z_fade,
        }
    elif isinstance(value, dict):
        missing = [name for name in FACE_NAMES if name not in value]
        if missing:
            raise ValueError(
                "fractal_noise.edge_fade_fraction is missing face(s): "
                + ", ".join(missing)
            )
        result = {name: float(value[name]) for name in FACE_NAMES}
    else:
        raise ValueError(
            "fractal_noise.edge_fade_fraction requires an XYZ array or face object"
        )
    if any(not math.isfinite(item) or item < 0.0 or item > 1.0
           for item in result.values()):
        raise ValueError(
            "fractal_noise.edge_fade_fraction values must be between 0 and 1"
        )
    return result


class CloudBoundary:
    """Validated axis-aligned or artist-authored vertical cloud prism."""

    def __init__(self, config, center, size, depth_slope, name):
        config = config or {}
        self.mode = str(config.get("mode", "axis_aligned"))
        self.name = name
        self.bottom_corners = None
        self.thickness = None
        self._plane = None
        self._edges = None

        base_min = tuple(center[axis] - 0.5 * size[axis] for axis in range(3))
        base_max = tuple(center[axis] + 0.5 * size[axis] for axis in range(3))
        if self.mode == "axis_aligned":
            far_y_offset = (
                float(depth_slope.get("far_y_offset", 0.0))
                if depth_slope.get("enabled", False)
                else 0.0
            )
            bounds_min = list(base_min)
            bounds_max = list(base_max)
            bounds_min[1] += min(0.0, far_y_offset)
            bounds_max[1] += max(0.0, far_y_offset)
            self.base_bounds_min = base_min
            self.base_bounds_max = base_max
            self.bounds_min = tuple(bounds_min)
            self.bounds_max = tuple(bounds_max)
            return

        if self.mode != "corner_prism":
            raise ValueError(f"{name}: unsupported cloud boundary mode {self.mode!r}")
        if depth_slope.get("enabled", False):
            raise ValueError(
                f"{name}: depth_slope must be disabled for a corner_prism boundary"
            )
        corners = config.get("bottom_corners")
        if not isinstance(corners, dict):
            raise ValueError(f"{name}: corner_prism.bottom_corners must be an object")
        missing = [corner for corner in CORNER_NAMES if corner not in corners]
        if missing:
            raise ValueError(
                f"{name}: corner_prism is missing bottom corner(s): "
                + ", ".join(missing)
            )
        parsed = []
        for corner_name in CORNER_NAMES:
            point = corners[corner_name]
            if (not isinstance(point, (list, tuple)) or len(point) != 3
                    or not all(isinstance(v, (int, float)) and math.isfinite(v)
                               for v in point)):
                raise ValueError(
                    f"{name}: boundary.bottom_corners.{corner_name} requires "
                    "three finite numbers"
                )
            parsed.append(tuple(float(v) for v in point))
        thickness = config.get("thickness")
        if (not isinstance(thickness, (int, float))
                or not math.isfinite(thickness) or thickness <= 0.0):
            raise ValueError(f"{name}: corner_prism.thickness must be positive")

        turns = [
            _cross2(parsed[index], parsed[(index + 1) % 4], parsed[(index + 2) % 4])
            for index in range(4)
        ]
        scale = max(
            max(abs(point[0]) + abs(point[2]) for point in parsed), 1.0
        )
        tolerance = 1e-10 * scale * scale
        if any(abs(turn) <= tolerance for turn in turns) or not (
            all(turn > 0.0 for turn in turns) or all(turn < 0.0 for turn in turns)
        ):
            raise ValueError(
                f"{name}: corner_prism bottom corners must form the named "
                "non-crossing convex XZ footprint"
            )

        p0, p1, p2, p3 = parsed
        determinant = ((p1[0] - p0[0]) * (p2[2] - p0[2])
                       - (p2[0] - p0[0]) * (p1[2] - p0[2]))
        if abs(determinant) <= tolerance:
            raise ValueError(f"{name}: corner_prism footprint has zero area")
        b = (((p1[1] - p0[1]) * (p2[2] - p0[2])
              - (p2[1] - p0[1]) * (p1[2] - p0[2])) / determinant)
        c = (((p1[0] - p0[0]) * (p2[1] - p0[1])
              - (p2[0] - p0[0]) * (p1[1] - p0[1])) / determinant)
        a = p0[1] - b * p0[0] - c * p0[2]
        plane_tolerance = max(1e-6, float(thickness) * 1e-8, scale * 1e-8)
        if abs((a + b * p3[0] + c * p3[2]) - p3[1]) > plane_tolerance:
            raise ValueError(
                f"{name}: corner_prism bottom corners must be coplanar"
            )

        centroid = tuple(sum(point[axis] for point in parsed) / 4.0
                         for axis in range(3))
        edge_indices = {
            "near": (0, 1), "right": (1, 2),
            "far": (2, 3), "left": (3, 0),
        }
        edges = {}
        for face, (begin, end) in edge_indices.items():
            interior = _cross2(parsed[begin], parsed[end], centroid)
            sign = 1.0 if interior > 0.0 else -1.0
            denominator = max(
                sign * _cross2(parsed[begin], parsed[end], point)
                for point in parsed
            )
            edges[face] = (parsed[begin], parsed[end], sign, denominator)

        self.bottom_corners = tuple(parsed)
        self.thickness = float(thickness)
        self._plane = (a, b, c)
        self._edges = edges
        # The legacy depth slope is anchored at the near face (zero offset
        # there). Anchoring explicit prisms at the near-edge midpoint makes a
        # rectangular slope-to-prism conversion preserve the 3D noise field.
        self.reference_bottom_y = 0.5 * (p0[1] + p1[1])
        top = [(point[0], point[1] + self.thickness, point[2]) for point in parsed]
        all_points = parsed + top
        self.bounds_min = tuple(min(point[axis] for point in all_points)
                                for axis in range(3))
        self.bounds_max = tuple(max(point[axis] for point in all_points)
                                for axis in range(3))
        self.base_bounds_min = self.bounds_min
        self.base_bounds_max = self.bounds_max

    def bottom_y(self, x, z):
        if self.mode == "axis_aligned":
            return self.base_bounds_min[1]
        a, b, c = self._plane
        return a + b * x + c * z

    def local_coordinates(self, x, y, z):
        """Return inward face coordinates in [0,1], or None if outside."""

        if self.mode == "axis_aligned":
            return None
        result = {}
        for face, (begin, end, sign, denominator) in self._edges.items():
            coordinate = sign * _cross2(begin, end, (x, y, z)) / denominator
            if coordinate < -1e-9:
                return None
            result[face] = coordinate
        bottom_y = self.bottom_y(x, z)
        vertical = (y - bottom_y) / self.thickness
        if vertical < -1e-9 or vertical > 1.0 + 1e-9:
            return None
        result["bottom"] = vertical
        result["top"] = 1.0 - vertical
        return result

    def contains(self, point):
        if self.mode == "axis_aligned":
            return all(self.bounds_min[axis] <= float(point[axis]) <= self.bounds_max[axis]
                       for axis in range(3))
        return self.local_coordinates(*(float(v) for v in point)) is not None

    def vertices(self):
        """Return eight points in the established PBRT box-mesh order."""

        if self.mode == "axis_aligned":
            x0, y0, z0 = self.bounds_min
            x1, y1, z1 = self.bounds_max
            return (
                (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
            )
        near_left, near_right, far_right, far_left = self.bottom_corners
        lift = lambda point: (point[0], point[1] + self.thickness, point[2])
        return (
            far_left, far_right, lift(far_right), lift(far_left),
            near_left, near_right, lift(near_right), lift(near_left),
        )

    def contract(self):
        if self.mode == "axis_aligned":
            return {"mode": "axis_aligned"}
        return {
            "mode": "corner_prism",
            "bottom_corners": {
                name: list(point)
                for name, point in zip(CORNER_NAMES, self.bottom_corners)
            },
            "thickness": self.thickness,
        }
