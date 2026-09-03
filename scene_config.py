"""Validated, formatting-preserving access to the authoritative scene JSON."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable


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

        camera = require(("scene", "camera"), dict)
        if camera is not None:
            look_at = camera.get("look_at", {})
            for name in ("eye", "look", "up"):
                vector = look_at.get(name)
                if not isinstance(vector, list) or len(vector) != 3 or not all(
                    isinstance(item, (int, float)) for item in vector
                ):
                    errors.append(f"camera.look_at.{name} must contain 3 numbers")
            fov = camera.get("fov")
            if not isinstance(fov, (int, float)) or not 0 < fov < 180:
                errors.append("camera.fov must be between 0 and 180 degrees")

        film = require(("scene", "film"), dict)
        if film is not None:
            for name in ("x_resolution", "y_resolution"):
                value = film.get(name)
                if not isinstance(value, int) or value <= 0:
                    errors.append(f"film.{name} must be a positive integer")

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
