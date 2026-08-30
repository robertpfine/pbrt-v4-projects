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
        landforms = self.get(("scene", "terrain", "landforms"))
        if not isinstance(landforms, dict):
            raise SceneConfigError("scene.terrain.landforms must be an object")
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

        terrain = require(("scene", "terrain"), dict)
        if terrain is not None:
            active = terrain.get("active_landform")
            landforms = terrain.get("landforms")
            if not isinstance(active, str) or not isinstance(landforms, dict):
                errors.append("terrain requires active_landform and landforms")
            elif active not in landforms:
                errors.append(f"unknown active landform: {active}")

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

        poppies = require(("scene", "terrain", "details", "poppies"), dict)
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
            if not isinstance(frustum.get("enabled", False), bool):
                errors.append("poppies visible-ground placement must be boolean")
            placement_reference = frustum.get("placement_reference", "root")
            if placement_reference not in {"root", "flower"}:
                errors.append(
                    "poppies.camera_frustum.placement_reference must be "
                    "root or flower"
                )

        grass = require(("scene", "terrain", "details", "grass"), dict)
        if grass is not None:
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
        grass = self.get(("scene", "terrain", "details", "grass"))
        poppies = self.get(("scene", "terrain", "details", "poppies"))
        grass_count = sum(
            int(layer.get("count", 0)) for layer in grass.get("layers", [])
        )
        return "\n".join((
            f"Landform: {self.get(('scene', 'terrain', 'active_landform'))}",
            f"Grass: {'enabled' if grass.get('enabled') else 'disabled'}, "
            f"{grass_count:,} tufts",
            f"Poppies: {'enabled' if poppies.get('enabled') else 'disabled'}, "
            f"{int(poppies.get('count', 0)):,} instances",
            f"Trees: {', '.join(enabled_trees) if enabled_trees else 'none'}",
            f"Fog: {'enabled' if self.get(('scene', 'fog', 'enabled'), False) else 'disabled'}",
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
