#!/usr/bin/env python3
"""Project enabled cloud boundaries into the configured camera frame."""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path

from clouds import configured_cloud_module, create_clouds


def _subtract(left, right):
    return tuple(float(left[index]) - float(right[index]) for index in range(3))


def _dot(left, right):
    return sum(left[index] * right[index] for index in range(3))


def _cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _normalize(vector):
    length = math.sqrt(_dot(vector, vector))
    if length <= 1e-12:
        raise ValueError("camera vectors must be nonzero")
    return tuple(component / length for component in vector)


def project_point(point, camera, film):
    """Return PBRT-perspective pixel coordinates and forward depth."""

    look_at = camera["look_at"]
    eye = tuple(float(value) for value in look_at["eye"])
    forward = _normalize(_subtract(look_at["look"], eye))
    right = _normalize(_cross(forward, look_at["up"]))
    camera_up = _cross(right, forward)
    relative = _subtract(point, eye)
    depth = _dot(relative, forward)
    width = int(film["x_resolution"])
    height = int(film["y_resolution"])
    if depth <= 0.0:
        return {
            "x": None, "y": None, "depth": depth,
            "in_front": False, "in_frame": False,
        }
    aspect = width / height
    tangent = math.tan(math.radians(float(camera["fov"])) / 2.0)
    half_x = tangent * max(aspect, 1.0)
    half_y = tangent * max(1.0 / aspect, 1.0)
    normalized_x = _dot(relative, right) / (depth * half_x)
    normalized_y = _dot(relative, camera_up) / (depth * half_y)
    pixel_x = (normalized_x + 1.0) * width / 2.0
    pixel_y = (1.0 - normalized_y) * height / 2.0
    return {
        "x": pixel_x,
        "y": pixel_y,
        "depth": depth,
        "in_front": True,
        "in_frame": 0.0 <= pixel_x <= width and 0.0 <= pixel_y <= height,
    }


def diagnose_formation(formation, camera, film):
    labels = (
        "far_left.bottom", "far_right.bottom", "far_right.top", "far_left.top",
        "near_left.bottom", "near_right.bottom", "near_right.top", "near_left.top",
    )
    vertices = formation.boundary.vertices()
    return {
        "name": formation.name,
        "mode": formation.boundary.mode,
        "camera_inside": formation.boundary.contains(camera["look_at"]["eye"]),
        "bounds_min": formation.bounds_min,
        "bounds_max": formation.bounds_max,
        "vertices": [
            {
                "label": label,
                "world": point,
                **project_point(point, camera, film),
            }
            for label, point in zip(labels, vertices)
        ],
    }


def diagnostic_svg(diagnostics, film):
    width = int(film["x_resolution"])
    height = int(film["y_resolution"])
    scale = min(1.0, 1200.0 / max(width, height))
    display_width = width * scale
    display_height = height * scale
    colors = ("#ff4d4d", "#3fd2ff", "#ffe45c", "#d66bff")
    edges = (
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    )
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{display_width:g}" '
        f'height="{display_height:g}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#20242a"/>',
    ]
    for cloud_index, diagnostic in enumerate(diagnostics):
        color = colors[cloud_index % len(colors)]
        vertices = diagnostic["vertices"]
        for begin, end in edges:
            left, right = vertices[begin], vertices[end]
            if not left["in_front"] or not right["in_front"]:
                continue
            lines.append(
                f'<line x1="{left["x"]:.3f}" y1="{left["y"]:.3f}" '
                f'x2="{right["x"]:.3f}" y2="{right["y"]:.3f}" '
                f'stroke="{color}" stroke-width="{2 / scale:g}"/>'
            )
        lines.append(
            f'<text x="{12 / scale:g}" y="{(24 + 22 * cloud_index) / scale:g}" '
            f'fill="{color}" font-size="{16 / scale:g}">'
            f'{html.escape(diagnostic["name"])} ({html.escape(diagnostic["mode"])})'
            '</text>'
        )
    lines.append('</svg>')
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("scene_workspace/config.json")
    )
    parser.add_argument("--cloud", help="inspect only this enabled cloud name")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--svg", type=Path, help="write a camera-frame wireframe SVG")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    formations = create_clouds(configured_cloud_module(config["scene_description"]["sky"]))
    if args.cloud:
        formations = [item for item in formations if item.name == args.cloud]
        if not formations:
            raise SystemExit(f"enabled cloud not found: {args.cloud}")
    camera = config["camera_settings"]
    film = config["render_settings"]["film"]
    diagnostics = [diagnose_formation(item, camera, film) for item in formations]
    if args.json:
        print(json.dumps(diagnostics, indent=2))
    else:
        for diagnostic in diagnostics:
            state = "INSIDE" if diagnostic["camera_inside"] else "outside"
            print(f'{diagnostic["name"]}: {diagnostic["mode"]}; camera {state}')
            for vertex in diagnostic["vertices"]:
                if not vertex["in_front"]:
                    projection = f'behind camera (depth {vertex["depth"]:.2f})'
                else:
                    frame = "in frame" if vertex["in_frame"] else "off frame"
                    projection = (
                        f'pixel ({vertex["x"]:.1f}, {vertex["y"]:.1f}), '
                        f'depth {vertex["depth"]:.2f}, {frame}'
                    )
                print(f'  {vertex["label"]}: {projection}')
    if args.svg:
        args.svg.parent.mkdir(parents=True, exist_ok=True)
        args.svg.write_text(diagnostic_svg(diagnostics, film), encoding="utf-8")
        print(f"wrote {args.svg}")


if __name__ == "__main__":
    main()
