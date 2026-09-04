"""Validated, formatting-preserving access to the authoritative scene JSON."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, time
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


JsonPath = tuple[str | int, ...]
_MISSING = object()
GROUND_PATH: JsonPath = ("scene", "landscape", "ground")
HILLS_PATH: JsonPath = ("scene", "landscape", "distant_hills")
SKY_PATH: JsonPath = ("scene", "sky")


class SceneConfigError(ValueError):
    """Raised when a scene configuration cannot be used safely."""


class SceneConfigConflictError(SceneConfigError):
    """Raised when the JSON changed on disk after it was loaded."""


class _JsonSpanParser:
    """Map JSON value paths to source spans without changing formatting."""

    def __init__(self, text: str):
        self.text = text
        self.length = len(text)
        self.index = 0
        self.decoder = json.JSONDecoder()
        self.spans: dict[JsonPath, tuple[int, int]] = {}

    def parse(self) -> dict[JsonPath, tuple[int, int]]:
        self._parse_value(())
        self._skip_space()
        if self.index != self.length:
            raise SceneConfigError(
                f"unexpected JSON content at character {self.index}"
            )
        return self.spans

    def _skip_space(self) -> None:
        while self.index < self.length and self.text[self.index].isspace():
            self.index += 1

    def _expect(self, character: str) -> None:
        self._skip_space()
        if self.index >= self.length or self.text[self.index] != character:
            raise SceneConfigError(
                f"expected {character!r} at character {self.index}"
            )
        self.index += 1

    def _decode_scalar(self) -> tuple[Any, int]:
        try:
            return self.decoder.raw_decode(self.text, self.index)
        except json.JSONDecodeError as error:
            raise SceneConfigError(str(error)) from error

    def _parse_value(self, path: JsonPath) -> None:
        self._skip_space()
        start = self.index
        if self.index >= self.length:
            raise SceneConfigError("unexpected end of JSON")
        token = self.text[self.index]
        if token == "{":
            self.index += 1
            self._skip_space()
            if self.index < self.length and self.text[self.index] == "}":
                self.index += 1
            else:
                while True:
                    self._skip_space()
                    key, end = self._decode_scalar()
                    if not isinstance(key, str):
                        raise SceneConfigError(
                            f"expected object key at character {self.index}"
                        )
                    self.index = end
                    self._expect(":")
                    self._parse_value(path + (key,))
                    self._skip_space()
                    if self.index < self.length and self.text[self.index] == ",":
                        self.index += 1
                        continue
                    self._expect("}")
                    break
        elif token == "[":
            self.index += 1
            self._skip_space()
            item_index = 0
            if self.index < self.length and self.text[self.index] == "]":
                self.index += 1
            else:
                while True:
                    self._parse_value(path + (item_index,))
                    item_index += 1
                    self._skip_space()
                    if self.index < self.length and self.text[self.index] == ",":
                        self.index += 1
                        continue
                    self._expect("]")
                    break
        else:
            _, self.index = self._decode_scalar()
        self.spans[path] = (start, self.index)


def _as_path(path: Iterable[str | int] | str) -> JsonPath:
    if isinstance(path, str):
        return tuple(int(part) if part.isdigit() else part for part in path.split("."))
    return tuple(path)


def _lookup(data: Any, path: JsonPath) -> Any:
    value = data
    for component in path:
        try:
            value = value[component]
        except (KeyError, IndexError, TypeError) as error:
            joined = ".".join(str(part) for part in path)
            raise SceneConfigError(f"unknown configuration path: {joined}") from error
    return value


class SceneConfig:
    """In-memory scene state backed by one authoritative JSON file.

    Existing source formatting is preserved by replacing only values explicitly
    changed through :meth:`set`. Direct manual editing remains fully supported;
    a save is refused if the file changed after this object loaded it.
    """

    def __init__(self, filename: str | os.PathLike[str]):
        self.path = Path(filename).resolve()
        self._source_text = ""
        self.data: dict[str, Any] = {}
        self._pending: dict[JsonPath, Any] = {}
        self.reload()
    def reload(self) -> None:
        try:
            text = self.path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, json.JSONDecodeError) as error:
            raise SceneConfigError(f"cannot load {self.path}: {error}") from error
        if not isinstance(data, dict):
            raise SceneConfigError("scene configuration root must be an object")
        self._source_text = text
        self.data = data
        self._pending.clear()

    @property
    def dirty(self) -> bool:
        return bool(self._pending)

    @property
    def changed_paths(self) -> tuple[JsonPath, ...]:
        return tuple(self._pending)

    def get(
        self,
        path: Iterable[str | int] | str,
        default: Any = _MISSING,
    ) -> Any:
        normalized = _as_path(path)
        try:
            return _lookup(self.data, normalized)
        except SceneConfigError:
            if default is not _MISSING:
                return default
            raise

    def set(self, path: Iterable[str | int] | str, value: Any) -> None:
        normalized = _as_path(path)
        current = _lookup(self.data, normalized)
        if isinstance(current, bool) and not isinstance(value, bool):
            raise SceneConfigError("boolean configuration value requires a boolean")
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise SceneConfigError("numeric configuration value requires a number")
        parent = _lookup(self.data, normalized[:-1]) if normalized[:-1] else self.data
        parent[normalized[-1]] = deepcopy(value)
        if value == _lookup(json.loads(self._source_text), normalized):
            self._pending.pop(normalized, None)
        else:
            self._pending[normalized] = deepcopy(value)

    def landform_names(self) -> tuple[str, ...]:
        landforms = self.get(GROUND_PATH + ("landforms",))
        if not isinstance(landforms, dict):
            raise SceneConfigError(
                "scene.landscape.ground.landforms must be an object"
            )
        return tuple(landforms)

    def validate(self) -> list[str]:
        errors: list[str] = []

        def require(path: JsonPath, expected: type | tuple[type, ...]) -> Any:
            try:
                value = self.get(path)
            except SceneConfigError as error:
                errors.append(str(error))
                return None
            if not isinstance(value, expected):
                errors.append(
                    f"{'.'.join(map(str, path))} has invalid type "
                    f"{type(value).__name__}"
                )
                return None
            return value

        def validate_depth_fade(owner: str, frustum: Any) -> None:
            if not isinstance(frustum, dict):
                errors.append(f"{owner}.camera_frustum must be an object")
                return
            fade = frustum.get("depth_fade", {})
            if not isinstance(fade, dict):
                errors.append(f"{owner}.camera_frustum.depth_fade must be an object")
                return
            if not fade.get("enabled", False):
                return
            start = fade.get("start")
            end = fade.get("end")
            minimum = fade.get("minimum_density", 0.0)
            if (
                not isinstance(start, (int, float))
                or not isinstance(end, (int, float))
                or start < 0
                or end <= start
            ):
                errors.append(
                    f"{owner}.camera_frustum.depth_fade requires 0 <= start < end"
                )
            if (
                not isinstance(minimum, (int, float))
                or not 0.0 <= minimum <= 1.0
            ):
                errors.append(
                    f"{owner}.camera_frustum.depth_fade.minimum_density "
                    "must be in [0, 1]"
                )

        file_names = require(("file_names",), dict)
        if file_names is not None:
            for name in ("pbrt_scene", "working_image", "archive_image"):
                value = file_names.get(name)
                if (
                    not isinstance(value, str)
                    or not value.strip()
                    or Path(value).is_absolute()
                    or value in (".", "..")
                    or len(Path(value).parts) != 1
                    or Path(value).name != value
                ):
                    errors.append(
                        f"file_names.{name} must be a filename without a directory"
                    )
            archive_image = file_names.get("archive_image")
            if isinstance(archive_image, str):
                if "{scene_name}" not in archive_image or "{timestamp}" not in archive_image:
                    errors.append(
                        "file_names.archive_image must contain {scene_name} and {timestamp}"
                    )
                resolved_archive = archive_image.replace(
                    "{scene_name}", "scene"
                ).replace("{timestamp}", "20000101_000000")
                if "{" in resolved_archive or "}" in resolved_archive:
                    errors.append(
                        "file_names.archive_image contains an unsupported placeholder"
                    )
                if Path(archive_image).suffix != ".png":
                    errors.append("file_names.archive_image must be a PNG filename")

        file_paths = require(("file_paths",), dict)
        if file_paths is not None:
            scene_files = file_paths.get("scene_files")
            if (
                not isinstance(scene_files, str)
                or not scene_files.strip()
                or Path(scene_files) == Path(".")
                or Path(scene_files).is_absolute()
                or ".." in Path(scene_files).parts
            ):
                errors.append(
                    "file_paths.scene_files must be a repository-relative path"
                )
            local_archive = file_paths.get("local_archive")
            if not isinstance(local_archive, str) or not local_archive.strip():
                errors.append("file_paths.local_archive must be a non-empty path")
            elif not Path(local_archive).is_absolute() and ".." in Path(local_archive).parts:
                errors.append(
                    "relative file_paths.local_archive must remain inside the repository"
                )
            remote_archive = file_paths.get("remote_archive")
            if not isinstance(remote_archive, str) or not remote_archive.strip():
                errors.append("file_paths.remote_archive must be a non-empty path")
            pbrt_executable = file_paths.get("pbrt_executable")
            if (
                not isinstance(pbrt_executable, str)
                or not Path(pbrt_executable).is_absolute()
            ):
                errors.append(
                    "file_paths.pbrt_executable must be an absolute path"
                )

        if "archive" in self.data:
            errors.append("obsolete archive root must be removed after file_paths migration")
        if "runtime" in self.data:
            errors.append("obsolete runtime root must be removed after render migration")
        if "pipeline" in self.data:
            errors.append("obsolete pipeline root must be removed after render migration")

        scene_description = require(("scene_description",), dict)
        if scene_description is not None:
            if scene_description.get("mode") != "new":
                errors.append("scene_description.mode must be new")
            scene_name = scene_description.get("name")
            if not isinstance(scene_name, str) or not scene_name.strip():
                errors.append("scene_description.name must be a non-empty name")

            context = scene_description.get("scene_context")
            if not isinstance(context, dict):
                errors.append("scene_description.scene_context must be an object")
            else:
                date_value = context.get("date")
                if (
                    not isinstance(date_value, str)
                    or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value)
                ):
                    errors.append("scene_context.date must use YYYY-MM-DD")
                else:
                    try:
                        date.fromisoformat(date_value)
                    except ValueError:
                        errors.append("scene_context.date must be a calendar date")

                time_value = context.get("local_time")
                if (
                    not isinstance(time_value, str)
                    or not re.fullmatch(r"\d{2}:\d{2}:\d{2}", time_value)
                ):
                    errors.append("scene_context.local_time must use HH:MM:SS")
                else:
                    try:
                        time.fromisoformat(time_value)
                    except ValueError:
                        errors.append("scene_context.local_time must be a valid time")

                time_zone = context.get("time_zone")
                if not isinstance(time_zone, str) or not time_zone.strip():
                    errors.append("scene_context.time_zone must be an IANA name")
                else:
                    try:
                        ZoneInfo(time_zone)
                    except (ValueError, ZoneInfoNotFoundError):
                        errors.append(
                            "scene_context.time_zone must be a valid IANA name"
                        )

                for field, minimum, maximum in (
                    ("latitude", -90.0, 90.0),
                    ("longitude", -180.0, 180.0),
                ):
                    value = context.get(field)
                    if (
                        not isinstance(value, (int, float))
                        or isinstance(value, bool)
                        or not math.isfinite(value)
                        or not minimum <= value <= maximum
                    ):
                        errors.append(
                            f"scene_context.{field} must be between "
                            f"{minimum:g} and {maximum:g}"
                        )

                world_north = context.get("world_north")
                if (
                    not isinstance(world_north, list)
                    or len(world_north) != 3
                    or any(
                        not isinstance(value, (int, float))
                        or isinstance(value, bool)
                        or not math.isfinite(value)
                        for value in world_north
                    )
                    or not math.isclose(world_north[1], 0.0, abs_tol=1e-9)
                    or math.hypot(world_north[0], world_north[2]) <= 1e-12
                ):
                    errors.append(
                        "scene_context.world_north must be a nonzero "
                        "horizontal vector"
                    )

        scene_root = self.get(("scene",), {})
        if isinstance(scene_root, dict):
            if "name" in scene_root:
                errors.append(
                    "obsolete scene.name must be removed after "
                    "scene_description migration"
                )
            for name in ("master_file", "output_filename", "generated_medium"):
                if name in scene_root:
                    errors.append(
                        f"obsolete scene.{name} must be removed after file_names migration"
                    )

        landscape = require(("scene", "landscape"), dict)
        ground = require(GROUND_PATH, dict) if landscape is not None else None
        if landscape is not None:
            distant_hills = landscape.get("distant_hills")
            if not isinstance(distant_hills, dict):
                errors.append("landscape requires a distant_hills module")
            elif not isinstance(distant_hills.get("enabled", False), bool):
                errors.append("distant_hills.enabled must be boolean")
            else:
                layers = distant_hills.get("layers")
                if layers is None and not distant_hills.get("enabled", False):
                    layers = []
                elif not isinstance(layers, list) or not layers:
                    errors.append("distant_hills.layers must contain at least one layer")
                if layers:
                    names = []
                    enabled_names = []
                    for index, layer in enumerate(layers):
                        prefix = f"distant_hills.layers.{index}"
                        if not isinstance(layer, dict):
                            errors.append(f"{prefix} must be an object")
                            continue
                        name = layer.get("name")
                        if not isinstance(name, str) or not name.strip():
                            errors.append(f"{prefix}.name must be a non-empty string")
                        else:
                            names.append(name)
                        if not isinstance(layer.get("enabled"), bool):
                            errors.append(f"{prefix}.enabled must be boolean")
                        elif layer.get("enabled") and isinstance(name, str):
                            enabled_names.append(name)
                        for field in ("center", "size", "resolution"):
                            value = layer.get(field)
                            if not isinstance(value, list) or len(value) != 2:
                                errors.append(f"{prefix}.{field} must contain two values")
                        size = layer.get("size", [])
                        if len(size) == 2 and not all(
                            isinstance(value, (int, float)) and value > 0
                            for value in size
                        ):
                            errors.append(f"{prefix}.size values must be positive")
                        resolution = layer.get("resolution", [])
                        if len(resolution) == 2 and not all(
                            isinstance(value, int) and value >= 2
                            for value in resolution
                        ):
                            errors.append(
                                f"{prefix}.resolution values must be integers at least 2"
                            )
                        ridge_position = layer.get("cross_section", {}).get(
                            "ridge_position"
                        )
                        if not isinstance(ridge_position, (int, float)) or not (
                            0.0 < ridge_position < 1.0
                        ):
                            errors.append(
                                f"{prefix}.cross_section.ridge_position must be "
                                "between 0 and 1"
                            )
                        peaks = layer.get("peaks", [])
                        ridge_profile = layer.get("ridge_profile", [])
                        if not isinstance(peaks, list):
                            errors.append(f"{prefix}.peaks must be an array")
                        elif peaks:
                            for peak_index, peak in enumerate(peaks):
                                peak_prefix = f"{prefix}.peaks.{peak_index}"
                                if not isinstance(peak, dict):
                                    errors.append(f"{peak_prefix} must be an object")
                                    continue
                                width = peak.get("width")
                                if not isinstance(width, (int, float)) or width <= 0:
                                    errors.append(f"{peak_prefix}.width must be positive")
                                asymmetry = peak.get("asymmetry")
                                if not isinstance(asymmetry, (int, float)) or not (
                                    -0.95 <= asymmetry <= 0.95
                                ):
                                    errors.append(
                                        f"{peak_prefix}.asymmetry must be in [-0.95, 0.95]"
                                    )
                        if not isinstance(ridge_profile, list):
                            errors.append(f"{prefix}.ridge_profile must be an array")
                        elif ridge_profile:
                            previous_position = None
                            if len(ridge_profile) < 2:
                                errors.append(
                                    f"{prefix}.ridge_profile must contain at least two points"
                                )
                            for point_index, point in enumerate(ridge_profile):
                                point_prefix = (
                                    f"{prefix}.ridge_profile.{point_index}"
                                )
                                if not isinstance(point, dict):
                                    errors.append(f"{point_prefix} must be an object")
                                    continue
                                position = point.get("position")
                                height = point.get("height")
                                if not isinstance(position, (int, float)) or not (
                                    -1.0 <= position <= 1.0
                                ):
                                    errors.append(
                                        f"{point_prefix}.position must be in [-1, 1]"
                                    )
                                elif (
                                    previous_position is not None
                                    and position <= previous_position
                                ):
                                    errors.append(
                                        f"{prefix}.ridge_profile positions must ascend"
                                    )
                                else:
                                    previous_position = position
                                if not isinstance(height, (int, float)) or height < 0:
                                    errors.append(
                                        f"{point_prefix}.height must be non-negative"
                                    )
                        elif not peaks:
                            errors.append(
                                f"{prefix} requires peaks or a ridge_profile"
                            )
                    if len(names) != len(set(names)):
                        errors.append("distant_hills layer names must be unique")
                    tree_line = distant_hills.get("tree_line", {})
                    if not isinstance(tree_line, dict):
                        errors.append("distant_hills.tree_line must be an object")
                    elif tree_line.get("enabled", False):
                        if tree_line.get("layer") not in enabled_names:
                            errors.append(
                                "distant_hills.tree_line.layer must name an active layer"
                            )
                        count = tree_line.get("count")
                        if not isinstance(count, int) or count < 0:
                            errors.append(
                                "distant_hills.tree_line.count must be non-negative"
                            )
                        for field in (
                            "lateral_range",
                            "height",
                            "crown_radius",
                            "evergreen_height",
                            "evergreen_crown_radius",
                        ):
                            value = tree_line.get(field)
                            if (
                                not isinstance(value, list)
                                or len(value) != 2
                                or not all(isinstance(item, (int, float)) for item in value)
                                or value[0] >= value[1]
                            ):
                                errors.append(
                                    f"distant_hills.tree_line.{field} must be an ascending pair"
                                )
                        variants = tree_line.get("reflectance_variants")
                        if (
                            not isinstance(variants, list)
                            or not variants
                            or any(
                                not isinstance(color, list)
                                or len(color) != 3
                                or not all(isinstance(value, (int, float)) for value in color)
                                for color in variants
                            )
                        ):
                            errors.append(
                                "distant_hills.tree_line.reflectance_variants must contain RGB triples"
                            )
                        evergreen_variants = tree_line.get(
                            "evergreen_reflectance_variants"
                        )
                        if (
                            not isinstance(evergreen_variants, list)
                            or not evergreen_variants
                            or any(
                                not isinstance(color, list)
                                or len(color) != 3
                                or not all(
                                    isinstance(value, (int, float))
                                    for value in color
                                )
                                for color in evergreen_variants
                            )
                            or (
                                isinstance(variants, list)
                                and len(evergreen_variants) != len(variants)
                            )
                        ):
                            errors.append(
                                "distant_hills.tree_line.evergreen_reflectance_variants "
                                "must match the deciduous RGB variants"
                            )
                        for field in ("evergreen_fraction", "clustered_fraction"):
                            value = tree_line.get(field)
                            if not isinstance(value, (int, float)) or not (
                                0.0 <= value <= 1.0
                            ):
                                errors.append(
                                    f"distant_hills.tree_line.{field} must be in [0, 1]"
                                )
            water = landscape.get("water")
            if not isinstance(water, dict):
                errors.append("landscape requires a water module")
            elif not isinstance(water.get("enabled", False), bool):
                errors.append("water.enabled must be boolean")
        if ground is not None:
            active = ground.get("active_landform")
            landforms = ground.get("landforms")
            if not isinstance(active, str) or not isinstance(landforms, dict):
                errors.append("landscape.ground requires active_landform and landforms")
            elif active not in landforms:
                errors.append(f"unknown active landform: {active}")

        sky = require(SKY_PATH, dict)
        if sky is not None:
            background = sky.get("background")
            clouds = sky.get("clouds")
            if not isinstance(background, dict):
                errors.append("sky requires a background module")
            elif background.get("type") != "infinite":
                errors.append("sky.background.type must be infinite")
            if not isinstance(clouds, dict):
                errors.append("sky requires a clouds module")
            elif not isinstance(clouds.get("enabled", False), bool):
                errors.append("sky.clouds.enabled must be boolean")

        rain = self.get(("scene", "rain"), None)
        if rain is not None:
            if not isinstance(rain, dict):
                errors.append("rain must be an object")
            elif not isinstance(rain.get("enabled", False), bool):
                errors.append("rain.enabled must be boolean")
            else:
                curtains = rain.get("curtains", [])
                if not isinstance(curtains, list):
                    errors.append("rain.curtains must be an array")
                else:
                    for index, curtain in enumerate(curtains):
                        prefix = f"rain.curtains.{index}"
                        if not isinstance(curtain, dict):
                            errors.append(f"{prefix} must be an object")
                            continue
                        if not isinstance(curtain.get("enabled", True), bool):
                            errors.append(f"{prefix}.enabled must be boolean")
                        for field in ("center", "size", "resolution"):
                            value = curtain.get(field)
                            if not isinstance(value, list) or len(value) != 3:
                                errors.append(f"{prefix}.{field} must contain three values")
                        size = curtain.get("size", [])
                        if len(size) == 3 and not all(
                            isinstance(value, (int, float)) and value > 0
                            for value in size
                        ):
                            errors.append(f"{prefix}.size values must be positive")
                        resolution = curtain.get("resolution", [])
                        if len(resolution) == 3 and not all(
                            isinstance(value, int) and value >= 2
                            for value in resolution
                        ):
                            errors.append(
                                f"{prefix}.resolution values must be integers at least 2"
                            )

        camera = require(("camera_settings",), dict)
        if camera is not None:
            if not isinstance(camera.get("enabled"), bool):
                errors.append("camera_settings.enabled must be boolean")
            if camera.get("type") != "perspective":
                errors.append("camera_settings.type must be perspective")
            look_at = camera.get("look_at", {})
            if not isinstance(look_at, dict):
                errors.append("camera_settings.look_at must be an object")
                look_at = {}
            valid_vectors: dict[str, list[float | int]] = {}
            for name in ("eye", "look", "up"):
                vector = look_at.get(name)
                if not isinstance(vector, list) or len(vector) != 3 or not all(
                    isinstance(item, (int, float))
                    and not isinstance(item, bool)
                    and math.isfinite(item)
                    for item in vector
                ):
                    errors.append(
                        f"camera_settings.look_at.{name} must contain 3 finite numbers"
                    )
                else:
                    valid_vectors[name] = vector
            if (
                "eye" in valid_vectors
                and "look" in valid_vectors
                and valid_vectors["eye"] == valid_vectors["look"]
            ):
                errors.append("camera_settings eye and look points must differ")
            if "up" in valid_vectors:
                up = valid_vectors["up"]
                if math.sqrt(sum(value * value for value in up)) <= 1e-12:
                    errors.append("camera_settings up vector must be nonzero")
            if all(name in valid_vectors for name in ("eye", "look", "up")):
                eye = valid_vectors["eye"]
                look = valid_vectors["look"]
                up = valid_vectors["up"]
                view = [look[index] - eye[index] for index in range(3)]
                cross = (
                    view[1] * up[2] - view[2] * up[1],
                    view[2] * up[0] - view[0] * up[2],
                    view[0] * up[1] - view[1] * up[0],
                )
                view_length = math.sqrt(sum(value * value for value in view))
                up_length = math.sqrt(sum(value * value for value in up))
                cross_length = math.sqrt(sum(value * value for value in cross))
                if cross_length <= 1e-12 * view_length * up_length:
                    errors.append(
                        "camera_settings up vector must not be parallel to view"
                    )
            fov = camera.get("fov")
            if (
                not isinstance(fov, (int, float))
                or isinstance(fov, bool)
                or not math.isfinite(fov)
                or not 0 < fov < 180
            ):
                errors.append(
                    "camera_settings.fov must be between 0 and 180 degrees"
                )

        scene_for_camera = self.get(("scene",), {})
        if isinstance(scene_for_camera, dict) and "camera" in scene_for_camera:
            errors.append(
                "obsolete scene.camera must be removed after camera_settings migration"
            )

        render_settings = require(("render_settings",), dict)
        film = (
            require(("render_settings", "film"), dict)
            if render_settings is not None else None
        )
        if film is not None:
            for name in ("x_resolution", "y_resolution"):
                value = film.get(name)
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    errors.append(
                        f"render_settings.film.{name} must be a positive integer"
                    )

        sampler = (
            require(("render_settings", "sampler"), dict)
            if render_settings is not None else None
        )
        if sampler is not None:
            if sampler.get("type") != "halton":
                errors.append("render_settings.sampler.type must be halton")
            pixel_samples = sampler.get("pixel_samples")
            if (
                not isinstance(pixel_samples, int)
                or isinstance(pixel_samples, bool)
                or pixel_samples <= 0
            ):
                errors.append(
                    "render_settings.sampler.pixel_samples must be a positive integer"
                )

        integrator = (
            require(("render_settings", "integrator"), dict)
            if render_settings is not None else None
        )
        if integrator is not None:
            if integrator.get("type") != "volpath":
                errors.append("render_settings.integrator.type must be volpath")
            max_depth = integrator.get("max_depth")
            if (
                not isinstance(max_depth, int)
                or isinstance(max_depth, bool)
                or max_depth <= 0
            ):
                errors.append(
                    "render_settings.integrator.max_depth must be a positive integer"
                )

        backend = (
            require(("render_settings", "backend"), dict)
            if render_settings is not None else None
        )
        if backend is not None:
            if backend.get("type") not in {"cpu", "gpu"}:
                errors.append("render_settings.backend.type must be cpu or gpu")
            if not isinstance(backend.get("show_statistics"), bool):
                errors.append(
                    "render_settings.backend.show_statistics must be boolean"
                )

        shaft = (
            require(("render_settings", "shaft_composite"), dict)
            if render_settings is not None else None
        )
        if shaft is not None:
            if not isinstance(shaft.get("enabled"), bool):
                errors.append(
                    "render_settings.shaft_composite.enabled must be boolean"
                )
            shaft_light = shaft.get("shaft_light")
            if not isinstance(shaft_light, str) or not shaft_light.strip():
                errors.append(
                    "render_settings.shaft_composite.shaft_light must be a name"
                )
            else:
                lights = self.get(("scene", "lights"), [])
                labels = {
                    light.get("label")
                    for light in lights
                    if isinstance(light, dict)
                }
                if shaft_light not in labels:
                    errors.append(
                        "render_settings.shaft_composite.shaft_light must resolve "
                        "to a scene light"
                    )
            for name in (
                "base_opacity",
                "shaft_opacity",
                "surface_reflectance_scale",
                "terrain_reflectance_scale",
                "blur_radius",
            ):
                value = shaft.get(name)
                if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(value)
                    or value < 0
                ):
                    errors.append(
                        f"render_settings.shaft_composite.{name} must be nonnegative"
                    )

        if isinstance(scene_for_camera, dict):
            for name in ("film", "sampler", "integrator"):
                if name in scene_for_camera:
                    errors.append(
                        f"obsolete scene.{name} must be removed after render migration"
                    )

        poppies = require(GROUND_PATH + ("details", "poppies"), dict)
        if poppies is not None:
            count = poppies.get("count")
            if not isinstance(count, int) or count < 0:
                errors.append("poppies.count must be a non-negative integer")
            scale = poppies.get("scale")
            if (
                not isinstance(scale, list)
                or len(scale) != 2
                or not all(isinstance(value, (int, float)) for value in scale)
                or scale[0] > scale[1]
            ):
                errors.append("poppies.scale must be an ascending pair")
            frustum = poppies.get("camera_frustum", {})
            validate_depth_fade("poppies", frustum)
            if isinstance(frustum, dict):
                if not isinstance(frustum.get("enabled", False), bool):
                    errors.append("poppies visible-ground placement must be boolean")
                placement_reference = frustum.get("placement_reference", "root")
                if placement_reference not in {"root", "flower"}:
                    errors.append(
                        "poppies.camera_frustum.placement_reference must be "
                        "root or flower"
                    )

        grass = require(GROUND_PATH + ("details", "grass"), dict)
        if grass is not None:
            validate_depth_fade("grass", grass.get("camera_frustum", {}))
            surface = grass.get("surface", {})
            if not isinstance(surface, dict):
                errors.append("grass.surface must be an object")
            elif surface.get("type", "diffuse") not in {"diffuse", "coateddiffuse"}:
                errors.append("grass.surface.type must be diffuse or coateddiffuse")
            layers = grass.get("layers", [])
            if not isinstance(layers, list) or not layers:
                errors.append("grass.layers must contain at least one layer")
            else:
                count = layers[0].get("count") if isinstance(layers[0], dict) else None
                if not isinstance(count, int) or count < 0:
                    errors.append("grass.layers.0.count must be non-negative")

        return errors

    def describe(self) -> str:
        scene_description = self.get(("scene_description",))
        context = scene_description["scene_context"]
        enabled_trees = []
        for entry in self.get(("scene", "lsystem_trees"), []):
            if entry.get("enabled", False):
                enabled_trees.append(entry.get("preset", "unnamed"))
        for index, entry in enumerate(self.get(("scene", "trees"), [])):
            if entry.get("enabled", False):
                enabled_trees.append(entry.get("name", f"space_colonization_{index}"))
        grass = self.get(GROUND_PATH + ("details", "grass"))
        poppies = self.get(GROUND_PATH + ("details", "poppies"))
        distant_hills = self.get(HILLS_PATH)
        water = self.get(("scene", "landscape", "water"))
        sky = self.get(SKY_PATH)
        rain = self.get(("scene", "rain"), {})
        grass_count = sum(
            int(layer.get("count", 0)) for layer in grass.get("layers", [])
        )
        hill_layer_count = sum(
            bool(layer.get("enabled"))
            for layer in distant_hills.get("layers", [])
        )
        return "\n".join((
            f"Scene: {scene_description['name']} ({scene_description['mode']})",
            f"Context: {context['date']} {context['local_time']} "
            f"{context['time_zone']}, {context['latitude']:.3f}, "
            f"{context['longitude']:.3f}",
            f"Landform: {self.get(GROUND_PATH + ('active_landform',))}",
            f"Grass: {'enabled' if grass.get('enabled') else 'disabled'}, "
            f"{grass_count:,} tufts",
            f"Poppies: {'enabled' if poppies.get('enabled') else 'disabled'}, "
            f"{int(poppies.get('count', 0)):,} instances",
            f"Trees: {', '.join(enabled_trees) if enabled_trees else 'none'}",
            f"Water: {'enabled' if water.get('enabled') else 'disabled'}",
            f"Distant hills: {'enabled' if distant_hills.get('enabled') else 'disabled'}, "
            f"{hill_layer_count} {'layer' if hill_layer_count == 1 else 'layers'}",
            f"Sky background: {'enabled' if sky['background'].get('enabled') else 'disabled'}",
            f"Clouds: {'enabled' if sky['clouds'].get('enabled') else 'disabled'}",
            f"Fog: {'enabled' if self.get(('scene', 'fog', 'enabled'), False) else 'disabled'}",
            f"Rain: {'enabled' if rain.get('enabled', False) else 'disabled'}, "
            f"{sum(bool(item.get('enabled', True)) for item in rain.get('curtains', []))} curtains",
        ))

    def save(self) -> None:
        if not self.dirty:
            return
        errors = self.validate()
        if errors:
            raise SceneConfigError("cannot save invalid scene:\n- " + "\n- ".join(errors))
        try:
            disk_text = self.path.read_text(encoding="utf-8")
        except OSError as error:
            raise SceneConfigError(f"cannot read {self.path}: {error}") from error
        if disk_text != self._source_text:
            raise SceneConfigConflictError(
                "config.json changed on disk; reload before saving GUI changes"
            )

        spans = _JsonSpanParser(self._source_text).parse()
        replacements = []
        for path, value in self._pending.items():
            if path not in spans:
                joined = ".".join(str(part) for part in path)
                raise SceneConfigError(f"cannot preserve unknown JSON path: {joined}")
            start, end = spans[path]
            encoded = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
            replacements.append((start, end, encoded))
        text = self._source_text
        for start, end, encoded in sorted(replacements, reverse=True):
            text = text[:start] + encoded + text[end:]
        try:
            json.loads(text)
        except json.JSONDecodeError as error:
            raise SceneConfigError(f"refusing to write invalid JSON: {error}") from error

        temporary_name = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(text)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, self.path)
        except OSError as error:
            if temporary_name:
                Path(temporary_name).unlink(missing_ok=True)
            raise SceneConfigError(f"cannot save {self.path}: {error}") from error
        self.reload()
