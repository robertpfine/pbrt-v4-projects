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
LANDFORMS_PATH: JsonPath = ("scene_description", "landforms")
OBJECTS_PATH: JsonPath = ("scene_description", "objects")
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
        landforms = self.get(LANDFORMS_PATH)
        if not isinstance(landforms, list):
            raise SceneConfigError(
                "scene_description.landforms must be an array"
            )
        return tuple(
            landform["name"]
            for landform in landforms
            if isinstance(landform, dict) and isinstance(landform.get("name"), str)
        )

    def terrain_landform_index(self) -> int:
        """Return the sole enabled terrain-heightfield landform index."""

        landforms = self.get(LANDFORMS_PATH)
        matches = [
            index
            for index, landform in enumerate(landforms)
            if isinstance(landform, dict)
            and landform.get("enabled", False)
            and isinstance(landform.get("topography"), dict)
            and landform["topography"].get("enabled", False)
            and landform["topography"].get("generator")
            == "terrain_heightfield"
        ]
        if len(matches) != 1:
            raise SceneConfigError(
                "scene requires exactly one enabled terrain_heightfield landform"
            )
        return matches[0]

    def surface_object_path(self, generator: str) -> JsonPath:
        """Return the unique path for a registered landform surface object."""

        matches = []
        for landform_index, landform in enumerate(self.get(LANDFORMS_PATH)):
            for object_index, item in enumerate(landform.get("surface_objects", [])):
                if item.get("generator") == generator:
                    matches.append(
                        LANDFORMS_PATH
                        + (landform_index, "surface_objects", object_index)
                    )
        if len(matches) != 1:
            raise SceneConfigError(
                f"scene requires exactly one {generator} surface object"
            )
        return matches[0]

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

            landforms = scene_description.get("landforms")
            if not isinstance(landforms, list):
                errors.append("scene_description.landforms must be an array")
            else:
                names: list[str] = []
                enabled_terrain_count = 0
                for index, landform in enumerate(landforms):
                    prefix = f"scene_description.landforms.{index}"
                    if not isinstance(landform, dict):
                        errors.append(f"{prefix} must be an object")
                        continue
                    name = landform.get("name")
                    if not isinstance(name, str) or not name.strip():
                        errors.append(f"{prefix}.name must be a non-empty string")
                    else:
                        names.append(name)
                    enabled = landform.get("enabled")
                    if not isinstance(enabled, bool):
                        errors.append(f"{prefix}.enabled must be boolean")

                    placement = landform.get("placement")
                    if not isinstance(placement, dict):
                        errors.append(f"{prefix}.placement must be an object")
                    else:
                        for field in ("position", "rotation_degrees"):
                            vector = placement.get(field)
                            if (
                                not isinstance(vector, list)
                                or len(vector) != 3
                                or any(
                                    not isinstance(value, (int, float))
                                    or isinstance(value, bool)
                                    or not math.isfinite(value)
                                    for value in vector
                                )
                            ):
                                errors.append(
                                    f"{prefix}.placement.{field} must contain "
                                    "3 finite numbers"
                                )

                    geometry = landform.get("geometry")
                    patches = (
                        geometry.get("patches")
                        if isinstance(geometry, dict)
                        else None
                    )
                    if not isinstance(patches, list) or not patches:
                        errors.append(f"{prefix}.geometry.patches must be a non-empty array")
                    else:
                        patch_names: list[str] = []
                        for patch_index, patch in enumerate(patches):
                            patch_prefix = (
                                f"{prefix}.geometry.patches.{patch_index}"
                            )
                            if not isinstance(patch, dict):
                                errors.append(f"{patch_prefix} must be an object")
                                continue
                            patch_name = patch.get("name")
                            if not isinstance(patch_name, str) or not patch_name.strip():
                                errors.append(
                                    f"{patch_prefix}.name must be a non-empty string"
                                )
                            else:
                                patch_names.append(patch_name)
                            if not isinstance(patch.get("enabled"), bool):
                                errors.append(f"{patch_prefix}.enabled must be boolean")
                            if patch.get("generator") != "plane":
                                errors.append(f"{patch_prefix}.generator must be plane")
                            dimensions = patch.get("dimensions")
                            if (
                                not isinstance(dimensions, list)
                                or len(dimensions) != 2
                                or any(
                                    not isinstance(value, (int, float))
                                    or isinstance(value, bool)
                                    or not math.isfinite(value)
                                    or value <= 0
                                    for value in dimensions
                                )
                            ):
                                errors.append(
                                    f"{patch_prefix}.dimensions must contain 2 positive numbers"
                                )
                            subdivisions = patch.get("subdivisions")
                            if (
                                not isinstance(subdivisions, list)
                                or len(subdivisions) != 2
                                or any(
                                    not isinstance(value, int)
                                    or isinstance(value, bool)
                                    or value < 2
                                    for value in subdivisions
                                )
                            ):
                                errors.append(
                                    f"{patch_prefix}.subdivisions must contain 2 integers at least 2"
                                )
                            for field in (
                                "local_position",
                                "local_rotation_degrees",
                            ):
                                vector = patch.get(field)
                                if (
                                    not isinstance(vector, list)
                                    or len(vector) != 3
                                    or any(
                                        not isinstance(value, (int, float))
                                        or isinstance(value, bool)
                                        or not math.isfinite(value)
                                        for value in vector
                                    )
                                ):
                                    errors.append(
                                        f"{patch_prefix}.{field} must contain 3 finite numbers"
                                    )
                        if len(patch_names) != len(set(patch_names)):
                            errors.append(f"{prefix}.geometry patch names must be unique")

                    topography = landform.get("topography")
                    if not isinstance(topography, dict):
                        errors.append(f"{prefix}.topography must be an object")
                    else:
                        topography_enabled = topography.get("enabled")
                        if not isinstance(topography_enabled, bool):
                            errors.append(f"{prefix}.topography.enabled must be boolean")
                        generator = topography.get("generator")
                        if topography_enabled is True:
                            if generator not in {
                                "terrain_heightfield",
                                "distant_ridge",
                            }:
                                errors.append(
                                    f"{prefix}.topography.generator must be "
                                    "terrain_heightfield or distant_ridge"
                                )
                            if not isinstance(topography.get("parameters"), dict):
                                errors.append(
                                    f"{prefix}.topography.parameters must be an object"
                                )
                        elif generator is not None and generator not in {
                            "terrain_heightfield",
                            "distant_ridge",
                        }:
                            errors.append(
                                f"{prefix}.topography.generator must be "
                                "terrain_heightfield or distant_ridge when provided"
                            )
                        if topography_enabled is True and generator == "terrain_heightfield":
                            rotations = []
                            if isinstance(placement, dict):
                                rotations.append(placement.get("rotation_degrees"))
                            if isinstance(patches, list):
                                rotations.extend(
                                    patch.get("local_rotation_degrees")
                                    for patch in patches
                                    if isinstance(patch, dict)
                                )
                            if any(
                                isinstance(rotation, list)
                                and len(rotation) == 3
                                and any(value != 0 for value in rotation)
                                for rotation in rotations
                            ):
                                errors.append(
                                    f"{prefix} terrain_heightfield rotations "
                                    "must currently be zero"
                                )
                        if topography_enabled is True and generator == "distant_ridge":
                            parameters = topography.get("parameters", {})
                            rotation = (
                                placement.get("rotation_degrees", [])
                                if isinstance(placement, dict)
                                else []
                            )
                            if (
                                len(rotation) == 3
                                and (rotation[0] != 0 or rotation[2] != 0)
                            ):
                                errors.append(
                                    f"{prefix} distant_ridge supports only Y rotation"
                                )
                            ridge_position = parameters.get(
                                "cross_section", {}
                            ).get("ridge_position")
                            if not isinstance(
                                ridge_position, (int, float)
                            ) or not (0.0 < ridge_position < 1.0):
                                errors.append(
                                    f"{prefix}.topography.parameters.cross_section."
                                    "ridge_position must be between 0 and 1"
                                )
                            peaks = parameters.get("peaks", [])
                            ridge_profile = parameters.get("ridge_profile", [])
                            if not isinstance(peaks, list):
                                errors.append(
                                    f"{prefix}.topography.parameters.peaks must be an array"
                                )
                            elif peaks:
                                for peak_index, peak in enumerate(peaks):
                                    peak_prefix = (
                                        f"{prefix}.topography.parameters.peaks."
                                        f"{peak_index}"
                                    )
                                    if not isinstance(peak, dict):
                                        errors.append(f"{peak_prefix} must be an object")
                                        continue
                                    width = peak.get("width")
                                    if not isinstance(
                                        width, (int, float)
                                    ) or width <= 0:
                                        errors.append(
                                            f"{peak_prefix}.width must be positive"
                                        )
                                    asymmetry = peak.get("asymmetry")
                                    if not isinstance(
                                        asymmetry, (int, float)
                                    ) or not (-0.95 <= asymmetry <= 0.95):
                                        errors.append(
                                            f"{peak_prefix}.asymmetry must be in "
                                            "[-0.95, 0.95]"
                                        )
                            if not isinstance(ridge_profile, list):
                                errors.append(
                                    f"{prefix}.topography.parameters.ridge_profile "
                                    "must be an array"
                                )
                            elif not ridge_profile and not peaks:
                                errors.append(
                                    f"{prefix} distant_ridge requires peaks or "
                                    "a ridge_profile"
                                )
                        if (
                            enabled is True
                            and topography_enabled is True
                            and generator == "terrain_heightfield"
                        ):
                            enabled_terrain_count += 1

                    surface = landform.get("surface")
                    if not isinstance(surface, dict):
                        errors.append(f"{prefix}.surface must be an object")
                    else:
                        for field in ("material", "texture"):
                            if not isinstance(surface.get(field), dict):
                                errors.append(f"{prefix}.surface.{field} must be an object")
                    surface_objects = landform.get("surface_objects")
                    if not isinstance(surface_objects, list):
                        errors.append(f"{prefix}.surface_objects must be an array")
                    else:
                        object_names: list[str] = []
                        for object_index, item in enumerate(surface_objects):
                            object_prefix = (
                                f"{prefix}.surface_objects.{object_index}"
                            )
                            if not isinstance(item, dict):
                                errors.append(f"{object_prefix} must be an object")
                                continue
                            object_name = item.get("name")
                            if not isinstance(object_name, str) or not object_name.strip():
                                errors.append(
                                    f"{object_prefix}.name must be a non-empty string"
                                )
                            else:
                                object_names.append(object_name)
                            if not isinstance(item.get("enabled"), bool):
                                errors.append(f"{object_prefix}.enabled must be boolean")
                            generator = item.get("generator")
                            if generator not in {
                                "grass",
                                "poppy",
                                "litter",
                                "rock_scatter",
                                "undergrowth",
                                "lsystem_tree",
                                "space_colonization_tree",
                            }:
                                errors.append(
                                    f"{object_prefix}.generator must be grass, poppy, "
                                    "litter, rock_scatter, undergrowth, lsystem_tree, "
                                    "or space_colonization_tree"
                                )
                            construction = item.get("construction")
                            population = item.get("population")
                            if not isinstance(construction, dict):
                                errors.append(
                                    f"{object_prefix}.construction must be an object"
                                )
                                construction = {}
                            if not isinstance(population, dict):
                                errors.append(
                                    f"{object_prefix}.population must be an object"
                                )
                                population = {}
                            if generator == "grass":
                                validate_depth_fade(
                                    "grass", population.get("camera_frustum", {})
                                )
                                grass_surface = construction.get("surface")
                                if not isinstance(grass_surface, dict):
                                    errors.append("grass.construction.surface must be an object")
                                elif grass_surface.get("type", "diffuse") not in {
                                    "diffuse",
                                    "coateddiffuse",
                                }:
                                    errors.append(
                                        "grass.construction.surface.type must be "
                                        "diffuse or coateddiffuse"
                                    )
                                layers = population.get("layers")
                                if not isinstance(layers, list) or not layers:
                                    errors.append(
                                        "grass.population.layers must contain at least one layer"
                                    )
                                else:
                                    count = (
                                        layers[0].get("count")
                                        if isinstance(layers[0], dict)
                                        else None
                                    )
                                    if not isinstance(count, int) or count < 0:
                                        errors.append(
                                            "grass.population.layers.0.count must be non-negative"
                                        )
                            elif generator == "poppy":
                                count = population.get("count")
                                if not isinstance(count, int) or count < 0:
                                    errors.append(
                                        "poppies.population.count must be a non-negative integer"
                                    )
                                scale = population.get("scale")
                                if (
                                    not isinstance(scale, list)
                                    or len(scale) != 2
                                    or not all(
                                        isinstance(value, (int, float))
                                        for value in scale
                                    )
                                    or scale[0] > scale[1]
                                ):
                                    errors.append(
                                        "poppies.population.scale must be an ascending pair"
                                    )
                                frustum = population.get("camera_frustum", {})
                                validate_depth_fade("poppies", frustum)
                                if isinstance(frustum, dict):
                                    if not isinstance(
                                        frustum.get("enabled", False), bool
                                    ):
                                        errors.append(
                                            "poppies visible-ground placement must be boolean"
                                        )
                                    placement_reference = frustum.get(
                                        "placement_reference", "root"
                                    )
                                    if placement_reference not in {"root", "flower"}:
                                        errors.append(
                                            "poppies.camera_frustum.placement_reference "
                                            "must be root or flower"
                                        )
                            elif generator == "litter":
                                count = population.get("count")
                                if not isinstance(count, int) or count < 0:
                                    errors.append(
                                        "litter.population.count must be non-negative"
                                    )
                                scale = construction.get("scale")
                                if (
                                    not isinstance(scale, list)
                                    or len(scale) != 2
                                    or not all(
                                        isinstance(value, (int, float))
                                        for value in scale
                                    )
                                    or scale[0] > scale[1]
                                ):
                                    errors.append(
                                        "litter.construction.scale must be an ascending pair"
                                    )
                            elif generator == "rock_scatter":
                                count = population.get("count")
                                if not isinstance(count, int) or count < 0:
                                    errors.append(
                                        "rocks.population.count must be non-negative"
                                    )
                                scale = construction.get("scale")
                                if (
                                    not isinstance(scale, list)
                                    or len(scale) != 2
                                    or not all(
                                        isinstance(value, (int, float))
                                        for value in scale
                                    )
                                    or scale[0] > scale[1]
                                ):
                                    errors.append(
                                        "rocks.construction.scale must be an ascending pair"
                                    )
                            elif generator == "undergrowth":
                                count = population.get("count")
                                if not isinstance(count, int) or count < 0:
                                    errors.append(
                                        "undergrowth.population.count must be non-negative"
                                    )
                                scale = construction.get("scale")
                                if (
                                    not isinstance(scale, list)
                                    or len(scale) != 2
                                    or not all(
                                        isinstance(value, (int, float))
                                        for value in scale
                                    )
                                    or scale[0] > scale[1]
                                ):
                                    errors.append(
                                        "undergrowth.construction.scale must be an ascending pair"
                                    )
                            elif generator == "lsystem_tree":
                                if construction.get("preset") not in {
                                    "christmas_tree",
                                    "live_oak",
                                    "fractal_tree",
                                }:
                                    errors.append(
                                        "lsystem_tree.construction.preset is unsupported"
                                    )
                                scale = construction.get("scale")
                                if not isinstance(
                                    scale, (int, float)
                                ) or isinstance(scale, bool) or scale <= 0:
                                    errors.append(
                                        "lsystem_tree.construction.scale must be positive"
                                    )
                                if population.get("method") != "explicit":
                                    errors.append(
                                        "lsystem_tree.population.method must be explicit"
                                    )
                                origin = population.get("origin")
                                if (
                                    not isinstance(origin, list)
                                    or len(origin) != 3
                                    or not all(
                                        isinstance(value, (int, float))
                                        and not isinstance(value, bool)
                                        for value in origin
                                    )
                                ):
                                    errors.append(
                                        "lsystem_tree.population.origin must contain "
                                        "three numbers"
                                    )
                                terrain_placement = population.get(
                                    "terrain_placement"
                                )
                                if not isinstance(terrain_placement, dict) or not isinstance(
                                    terrain_placement.get("enabled"), bool
                                ):
                                    errors.append(
                                        "lsystem_tree.population.terrain_placement "
                                        "must contain enabled"
                                    )
                                instances = population.get("instances")
                                if not isinstance(instances, list):
                                    errors.append(
                                        "lsystem_tree.population.instances must be an array"
                                    )
                                else:
                                    for instance_index, instance in enumerate(instances):
                                        instance_prefix = (
                                            "lsystem_tree.population.instances."
                                            f"{instance_index}"
                                        )
                                        if not isinstance(instance, dict):
                                            errors.append(
                                                f"{instance_prefix} must be an object"
                                            )
                                            continue
                                        position = instance.get("position")
                                        if (
                                            not isinstance(position, list)
                                            or len(position) != 3
                                            or not all(
                                                isinstance(value, (int, float))
                                                and not isinstance(value, bool)
                                                for value in position
                                            )
                                        ):
                                            errors.append(
                                                f"{instance_prefix}.position must "
                                                "contain three numbers"
                                            )
                                        instance_scale = instance.get("scale")
                                        if not isinstance(
                                            instance_scale, (int, float)
                                        ) or isinstance(
                                            instance_scale, bool
                                        ) or instance_scale <= 0:
                                            errors.append(
                                                f"{instance_prefix}.scale must be positive"
                                            )
                            elif generator == "space_colonization_tree":
                                for field in ("num_leaves", "max_loops"):
                                    value = construction.get(field)
                                    if not isinstance(value, int) or value < 0:
                                        errors.append(
                                            "space_colonization_tree.construction."
                                            f"{field} must be non-negative"
                                        )
                                if not isinstance(construction.get("foliage"), dict):
                                    errors.append(
                                        "space_colonization_tree.construction.foliage "
                                        "must be an object"
                                    )
                                if population.get("method") != "explicit":
                                    errors.append(
                                        "space_colonization_tree.population.method "
                                        "must be explicit"
                                    )
                                root_position = population.get("root_position")
                                if (
                                    not isinstance(root_position, list)
                                    or len(root_position) != 3
                                    or not all(
                                        isinstance(value, (int, float))
                                        and not isinstance(value, bool)
                                        for value in root_position
                                    )
                                ):
                                    errors.append(
                                        "space_colonization_tree.population."
                                        "root_position must contain three numbers"
                                    )
                                instances = population.get("instances")
                                if not isinstance(instances, dict):
                                    errors.append(
                                        "space_colonization_tree.population.instances "
                                        "must be an object"
                                    )
                                else:
                                    if not isinstance(instances.get("enabled"), bool):
                                        errors.append(
                                            "space_colonization_tree.population.instances."
                                            "enabled must be boolean"
                                        )
                                    placements = instances.get("placements")
                                    if not isinstance(placements, list):
                                        errors.append(
                                            "space_colonization_tree.population.instances."
                                            "placements must be an array"
                                        )
                                    else:
                                        for placement_index, tree_placement in enumerate(placements):
                                            placement_prefix = (
                                                "space_colonization_tree.population."
                                                f"instances.placements.{placement_index}"
                                            )
                                            if not isinstance(tree_placement, dict):
                                                errors.append(
                                                    f"{placement_prefix} must be an object"
                                                )
                                                continue
                                            position = tree_placement.get("position")
                                            if (
                                                not isinstance(position, list)
                                                or len(position) != 3
                                            ):
                                                errors.append(
                                                    f"{placement_prefix}.position must "
                                                    "contain three values"
                                                )
                                            scale = tree_placement.get("scale")
                                            if not isinstance(
                                                scale, (int, float)
                                            ) or isinstance(
                                                scale, bool
                                            ) or scale <= 0:
                                                errors.append(
                                                    f"{placement_prefix}.scale must be positive"
                                                )
                        if len(object_names) != len(set(object_names)):
                            errors.append(f"{prefix}.surface object names must be unique")

                if len(names) != len(set(names)):
                    errors.append("scene_description.landform names must be unique")
                if enabled_terrain_count != 1:
                    errors.append(
                        "scene requires exactly one enabled terrain_heightfield landform"
                    )

            objects = scene_description.get("objects")
            if not isinstance(objects, list):
                errors.append("scene_description.objects must be an array")
            else:
                object_names: list[str] = []
                for index, item in enumerate(objects):
                    prefix = f"scene_description.objects.{index}"
                    if not isinstance(item, dict):
                        errors.append(f"{prefix} must be an object")
                        continue
                    name = item.get("name")
                    if not isinstance(name, str) or not name.strip():
                        errors.append(f"{prefix}.name must be a non-empty string")
                    else:
                        object_names.append(name)
                    if not isinstance(item.get("enabled"), bool):
                        errors.append(f"{prefix}.enabled must be boolean")
                    placement = item.get("placement")
                    if not isinstance(placement, dict):
                        errors.append(f"{prefix}.placement must be an object")
                    else:
                        for field in ("position", "rotation_degrees"):
                            vector = placement.get(field)
                            if (
                                not isinstance(vector, list)
                                or len(vector) != 3
                                or any(
                                    not isinstance(value, (int, float))
                                    or isinstance(value, bool)
                                    or not math.isfinite(value)
                                    for value in vector
                                )
                            ):
                                errors.append(
                                    f"{prefix}.placement.{field} must contain "
                                    "3 finite numbers"
                                )
                    geometry = item.get("geometry")
                    if not isinstance(geometry, dict):
                        errors.append(f"{prefix}.geometry must be an object")
                    else:
                        sources = [
                            field
                            for field in ("pbrt_shape", "generator")
                            if field in geometry
                        ]
                        if len(sources) != 1:
                            errors.append(
                                f"{prefix}.geometry requires exactly one of "
                                "pbrt_shape or generator"
                            )
                        elif geometry.get("generator") not in {
                            None,
                            "planar_phyllotaxis",
                            "box",
                        }:
                            errors.append(
                                f"{prefix}.geometry.generator is not registered"
                            )
                    if not isinstance(item.get("material"), dict):
                        errors.append(f"{prefix}.material must be an object")
                    construction = item.get("construction")
                    if isinstance(geometry, dict) and "generator" in geometry:
                        if not isinstance(construction, dict):
                            errors.append(f"{prefix}.construction must be an object")
                        elif geometry.get("generator") == "planar_phyllotaxis":
                            count = construction.get("count")
                            spacing = construction.get("spacing")
                            center = construction.get("center")
                            zones = construction.get("zones")
                            if not isinstance(count, int) or count < 0:
                                errors.append(
                                    f"{prefix}.construction.count must be non-negative"
                                )
                            if (
                                not isinstance(spacing, (int, float))
                                or isinstance(spacing, bool)
                                or spacing <= 0
                            ):
                                errors.append(
                                    f"{prefix}.construction.spacing must be positive"
                                )
                            if (
                                not isinstance(center, list)
                                or len(center) != 3
                                or not all(
                                    isinstance(value, (int, float))
                                    and not isinstance(value, bool)
                                    for value in center
                                )
                            ):
                                errors.append(
                                    f"{prefix}.construction.center must contain "
                                    "three numbers"
                                )
                            if not isinstance(zones, list) or not zones:
                                errors.append(
                                    f"{prefix}.construction.zones must be a "
                                    "non-empty array"
                                )
                        elif geometry.get("generator") == "box":
                            for minimum, maximum in (
                                ("x_min", "x_max"),
                                ("y_min", "y_max"),
                                ("z_min", "z_max"),
                            ):
                                low = construction.get(minimum)
                                high = construction.get(maximum)
                                if (
                                    not isinstance(low, (int, float))
                                    or isinstance(low, bool)
                                    or not isinstance(high, (int, float))
                                    or isinstance(high, bool)
                                    or low >= high
                                ):
                                    errors.append(
                                        f"{prefix}.construction requires {minimum} "
                                        f"less than {maximum}"
                                    )
                    if isinstance(geometry, dict) and "pbrt_shape" in geometry:
                        if geometry.get("pbrt_shape") != "sphere":
                            errors.append(
                                f"{prefix}.geometry.pbrt_shape is not supported"
                            )
                        parameters = geometry.get("parameters")
                        radius = (
                            parameters.get("radius")
                            if isinstance(parameters, dict)
                            else None
                        )
                        if (
                            not isinstance(radius, (int, float))
                            or isinstance(radius, bool)
                            or radius <= 0
                        ):
                            errors.append(
                                f"{prefix}.geometry.parameters.radius must be positive"
                            )
                    medium = item.get("medium")
                    if medium is not None:
                        if not isinstance(medium, dict):
                            errors.append(f"{prefix}.medium must be an object")
                        else:
                            interior = medium.get("interior")
                            if not isinstance(interior, dict):
                                errors.append(
                                    f"{prefix}.medium.interior must be an object"
                                )
                            elif interior.get("type") != "rgbgrid":
                                errors.append(
                                    f"{prefix}.medium.interior.type must be rgbgrid"
                                )
                            else:
                                if not isinstance(interior.get("name"), str) or not interior["name"].strip():
                                    errors.append(
                                        f"{prefix}.medium.interior.name must be non-empty"
                                    )
                                for field in ("nx", "ny", "nz"):
                                    value = interior.get(field)
                                    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                                        errors.append(
                                            f"{prefix}.medium.interior.{field} must be positive"
                                        )
                                if interior.get("axis") not in {"X", "Y", "Z"}:
                                    errors.append(
                                        f"{prefix}.medium.interior.axis must be X, Y, or Z"
                                    )
                                for field in ("world_min", "world_max"):
                                    vector = interior.get(field)
                                    if not isinstance(vector, list) or len(vector) != 3:
                                        errors.append(
                                            f"{prefix}.medium.interior.{field} must "
                                            "contain three values"
                                        )
                                if not isinstance(interior.get("zones"), list) or not interior["zones"]:
                                    errors.append(
                                        f"{prefix}.medium.interior.zones must be non-empty"
                                    )
                            if not isinstance(medium.get("exterior"), str):
                                errors.append(
                                    f"{prefix}.medium.exterior must be a string"
                                )
                if len(object_names) != len(set(object_names)):
                    errors.append("scene_description object names must be unique")

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
            if "lsystem_trees" in scene_root:
                errors.append(
                    "obsolete scene.lsystem_trees must be removed after "
                    "L-system tree migration"
                )
            for name in ("trees", "grove"):
                if name in scene_root:
                    errors.append(
                        f"obsolete scene.{name} must be removed after "
                        "space-colonization tree migration"
                    )
            if "planar_phyllotaxis" in scene_root:
                errors.append(
                    "obsolete scene.planar_phyllotaxis must be removed after "
                    "independent-object migration"
                )
            for name in ("grid", "zones"):
                if name in scene_root:
                    errors.append(
                        f"obsolete scene.{name} must be removed after "
                        "independent-volume migration"
                    )
            geometry = scene_root.get("geometry", [])
            if isinstance(geometry, list) and any(
                isinstance(item, dict) and item.get("label") == "vista_plane"
                for item in geometry
            ):
                errors.append(
                    "obsolete scene.geometry vista_plane must be removed after "
                    "vista landform migration"
                )
            if isinstance(geometry, list) and any(
                isinstance(item, dict)
                and item.get("label") in {"volume_sphere", "volume_box"}
                for item in geometry
            ):
                errors.append(
                    "obsolete scene.geometry independent volumes must be removed "
                    "after independent-volume migration"
                )

        landscape = require(("scene", "landscape"), dict)
        ground = landscape.get("ground") if landscape is not None else None
        if landscape is not None:
            distant_hills = landscape.get("distant_hills")
            if distant_hills is None:
                pass
            elif not isinstance(distant_hills, dict):
                errors.append("obsolete landscape.distant_hills must be an object")
            elif not isinstance(distant_hills.get("enabled", False), bool):
                errors.append("distant_hills.enabled must be boolean")
            else:
                errors.append(
                    "obsolete scene.landscape.distant_hills must be removed "
                    "after distant-ridge migration"
                )
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
            errors.append(
                "obsolete scene.landscape.ground must be removed after "
                "surface-object migration"
            )
        if isinstance(ground, dict):
            for name in ("enabled", "active_landform", "landforms", "material"):
                if name in ground:
                    errors.append(
                        f"obsolete scene.landscape.ground.{name} must be removed "
                        "after landform migration"
                    )
            details = ground.get("details")
            if not isinstance(details, dict):
                errors.append("landscape.ground.details must be an object")
            elif "surface" in details:
                errors.append(
                    "obsolete scene.landscape.ground.details.surface must be "
                    "removed after landform migration"
                )
            if isinstance(details, dict) and "grass" in details:
                errors.append(
                    "obsolete scene.landscape.ground.details.grass must be "
                    "removed after grass migration"
                )
            if isinstance(details, dict) and "poppies" in details:
                errors.append(
                    "obsolete scene.landscape.ground.details.poppies must be "
                    "removed after poppy migration"
                )
            if isinstance(details, dict) and "litter" in details:
                errors.append(
                    "obsolete scene.landscape.ground.details.litter must be "
                    "removed after litter migration"
                )
            if isinstance(details, dict) and "rocks" in details:
                errors.append(
                    "obsolete scene.landscape.ground.details.rocks must be "
                    "removed after rock migration"
                )
            if isinstance(details, dict) and "undergrowth" in details:
                errors.append(
                    "obsolete scene.landscape.ground.details.undergrowth must be "
                    "removed after undergrowth migration"
                )

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
        grass_object = self.get(self.surface_object_path("grass"))
        grass = {
            "enabled": grass_object["enabled"],
            **grass_object["construction"],
            **grass_object["population"],
        }
        poppy_object = self.get(self.surface_object_path("poppy"))
        poppies = {
            "enabled": poppy_object["enabled"],
            **poppy_object["construction"],
            **poppy_object["population"],
        }
        distant_hills = [
            landform
            for landform in self.get(LANDFORMS_PATH)
            if landform.get("topography", {}).get("generator") == "distant_ridge"
        ]
        water = self.get(("scene", "landscape", "water"))
        sky = self.get(SKY_PATH)
        rain = self.get(("scene", "rain"), {})
        grass_count = sum(
            int(layer.get("count", 0)) for layer in grass.get("layers", [])
        )
        hill_layer_count = sum(bool(landform.get("enabled")) for landform in distant_hills)
        return "\n".join((
            f"Scene: {scene_description['name']} ({scene_description['mode']})",
            f"Context: {context['date']} {context['local_time']} "
            f"{context['time_zone']}, {context['latitude']:.3f}, "
            f"{context['longitude']:.3f}",
            "Landform: " + ", ".join(
                landform.get("name", "unnamed")
                for landform in self.get(LANDFORMS_PATH)
                if landform.get("enabled", False)
            ),
            f"Grass: {'enabled' if grass.get('enabled') else 'disabled'}, "
            f"{grass_count:,} tufts",
            f"Poppies: {'enabled' if poppies.get('enabled') else 'disabled'}, "
            f"{int(poppies.get('count', 0)):,} instances",
            f"Trees: {', '.join(enabled_trees) if enabled_trees else 'none'}",
            f"Water: {'enabled' if water.get('enabled') else 'disabled'}",
            f"Distant hills: {'enabled' if hill_layer_count else 'disabled'}, "
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
