#!/usr/bin/env python3
"""Create and archive immutable PBRT-v4 Art Studio render inputs."""

from __future__ import annotations

import argparse
from datetime import date, datetime, time
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tarfile
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


RUN_DIRECTORY = Path("scene_workspace") / ".render_runs"
SCENE_DIRECTORY = Path("scene_workspace")
TIMESTAMP_PATTERN = re.compile(r"^\d{8}_\d{6}$")
ARTIFACT_SUFFIX_PATTERN = re.compile(r"^[._][A-Za-z0-9][A-Za-z0-9_.-]*$")


class RenderSnapshotError(RuntimeError):
    """Raised when a render snapshot cannot be created safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def archive_stem(scene_name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", scene_name).strip("_")
    return value or "untitled_scene"


def configured_scene_name(config: dict) -> str:
    """Validate the Stage 4 scene shell and return its required name."""

    description = config.get("scene_description")
    if not isinstance(description, dict):
        raise RenderSnapshotError("scene configuration requires scene_description")
    if description.get("mode") != "new":
        raise RenderSnapshotError("scene_description.mode must be new")
    name = description.get("name")
    if not isinstance(name, str) or not name.strip():
        raise RenderSnapshotError("scene_description.name requires a non-empty name")

    context = description.get("scene_context")
    if not isinstance(context, dict):
        raise RenderSnapshotError("scene_description.scene_context must be an object")
    date_value = context.get("date")
    if not isinstance(date_value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
        raise RenderSnapshotError("scene_context.date must use YYYY-MM-DD")
    try:
        date.fromisoformat(date_value)
    except ValueError as error:
        raise RenderSnapshotError("scene_context.date must be a calendar date") from error

    time_value = context.get("local_time")
    if not isinstance(time_value, str) or not re.fullmatch(r"\d{2}:\d{2}:\d{2}", time_value):
        raise RenderSnapshotError("scene_context.local_time must use HH:MM:SS")
    try:
        time.fromisoformat(time_value)
    except ValueError as error:
        raise RenderSnapshotError("scene_context.local_time must be a valid time") from error

    time_zone = context.get("time_zone")
    if not isinstance(time_zone, str) or not time_zone.strip():
        raise RenderSnapshotError("scene_context.time_zone requires an IANA name")
    try:
        ZoneInfo(time_zone)
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise RenderSnapshotError("scene_context.time_zone must be a valid IANA name") from error

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
            raise RenderSnapshotError(
                f"scene_context.{field} must be between {minimum:g} and {maximum:g}"
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
        raise RenderSnapshotError(
            "scene_context.world_north must be a nonzero horizontal vector"
        )

    scene = config.get("scene")
    if isinstance(scene, dict) and "name" in scene:
        raise RenderSnapshotError("obsolete scene.name is not supported")
    landforms = description.get("landforms")
    if not isinstance(landforms, list):
        raise RenderSnapshotError("scene_description.landforms must be an array")
    enabled_terrain = [
        landform
        for landform in landforms
        if isinstance(landform, dict)
        and landform.get("enabled", False)
        and isinstance(landform.get("topography"), dict)
        and landform["topography"].get("enabled", False)
        and landform["topography"].get("generator") == "terrain_heightfield"
    ]
    if len(enabled_terrain) != 1:
        raise RenderSnapshotError(
            "scene requires exactly one enabled terrain_heightfield landform"
        )
    grass_objects = [
        item
        for landform in landforms
        if isinstance(landform, dict)
        for item in landform.get("surface_objects", [])
        if isinstance(item, dict) and item.get("generator") == "grass"
    ]
    if grass_objects and (
        len(grass_objects) != 1
        or not isinstance(grass_objects[0].get("construction"), dict)
        or not isinstance(grass_objects[0].get("population"), dict)
    ):
        raise RenderSnapshotError(
            "grass requires one surface object with construction and population"
        )
    poppy_objects = [
        item
        for landform in landforms
        if isinstance(landform, dict)
        for item in landform.get("surface_objects", [])
        if isinstance(item, dict) and item.get("generator") == "poppy"
    ]
    if poppy_objects and (
        len(poppy_objects) != 1
        or not isinstance(poppy_objects[0].get("construction"), dict)
        or not isinstance(poppy_objects[0].get("population"), dict)
    ):
        raise RenderSnapshotError(
            "poppy requires one surface object with construction and population"
        )
    litter_objects = [
        item
        for landform in landforms
        if isinstance(landform, dict)
        for item in landform.get("surface_objects", [])
        if isinstance(item, dict) and item.get("generator") == "litter"
    ]
    if litter_objects and (
        len(litter_objects) != 1
        or not isinstance(litter_objects[0].get("construction"), dict)
        or not isinstance(litter_objects[0].get("population"), dict)
    ):
        raise RenderSnapshotError(
            "litter requires one surface object with construction and population"
        )
    rock_objects = [
        item
        for landform in landforms
        if isinstance(landform, dict)
        for item in landform.get("surface_objects", [])
        if isinstance(item, dict) and item.get("generator") == "rock_scatter"
    ]
    if rock_objects and (
        len(rock_objects) != 1
        or not isinstance(rock_objects[0].get("construction"), dict)
        or not isinstance(rock_objects[0].get("population"), dict)
    ):
        raise RenderSnapshotError(
            "rock_scatter requires one surface object with construction and population"
        )
    undergrowth_objects = [
        item
        for landform in landforms
        if isinstance(landform, dict)
        for item in landform.get("surface_objects", [])
        if isinstance(item, dict) and item.get("generator") == "undergrowth"
    ]
    if undergrowth_objects and (
        len(undergrowth_objects) != 1
        or not isinstance(undergrowth_objects[0].get("construction"), dict)
        or not isinstance(undergrowth_objects[0].get("population"), dict)
    ):
        raise RenderSnapshotError(
            "undergrowth requires one surface object with construction and population"
        )
    landscape = scene.get("landscape", {}) if isinstance(scene, dict) else {}
    ground = (
        landscape.get("ground", {}) if isinstance(landscape, dict) else {}
    )
    if isinstance(ground, dict):
        for field in ("enabled", "active_landform", "landforms", "material"):
            if field in ground:
                raise RenderSnapshotError(
                    f"obsolete scene.landscape.ground.{field} is not supported"
                )
        details = ground.get("details", {})
        if isinstance(details, dict) and "surface" in details:
            raise RenderSnapshotError(
                "obsolete scene.landscape.ground.details.surface is not supported"
            )
        if isinstance(details, dict) and "grass" in details:
            raise RenderSnapshotError(
                "obsolete scene.landscape.ground.details.grass is not supported"
            )
        if isinstance(details, dict) and "poppies" in details:
            raise RenderSnapshotError(
                "obsolete scene.landscape.ground.details.poppies is not supported"
            )
        if isinstance(details, dict) and "litter" in details:
            raise RenderSnapshotError(
                "obsolete scene.landscape.ground.details.litter is not supported"
            )
        if isinstance(details, dict) and "rocks" in details:
            raise RenderSnapshotError(
                "obsolete scene.landscape.ground.details.rocks is not supported"
            )
        if isinstance(details, dict) and "undergrowth" in details:
            raise RenderSnapshotError(
                "obsolete scene.landscape.ground.details.undergrowth is not supported"
            )
    if isinstance(landscape, dict) and "ground" in landscape:
        raise RenderSnapshotError("obsolete scene.landscape.ground is not supported")
    return name


def _filename(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RenderSnapshotError(f"{label} requires a non-empty filename")
    path = Path(value)
    if (
        path.is_absolute()
        or value in (".", "..")
        or len(path.parts) != 1
        or path.name != value
    ):
        raise RenderSnapshotError(f"{label} must be a filename without a directory")
    return value


def scene_files_relative(config: dict) -> Path:
    value = config.get("file_paths", {}).get("scene_files")
    if not isinstance(value, str) or not value.strip():
        raise RenderSnapshotError("file_paths.scene_files requires a repository-relative path")
    path = Path(value)
    if path == Path(".") or path.is_absolute() or ".." in path.parts:
        raise RenderSnapshotError(
            "file_paths.scene_files must remain inside the frozen repository"
        )
    return path


def resolve_local_archive(config: dict, repository_root: Path) -> Path:
    value = config.get("file_paths", {}).get("local_archive")
    if not isinstance(value, str) or not value.strip():
        raise RenderSnapshotError("file_paths.local_archive requires a path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        if ".." in path.parts:
            raise RenderSnapshotError(
                "relative file_paths.local_archive must remain inside the repository"
            )
        path = repository_root / path
    return path.resolve()


def archive_image_name(config: dict, timestamp: str) -> str:
    pattern = config.get("file_names", {}).get("archive_image")
    pattern = _filename(pattern, "file_names.archive_image")
    if "{scene_name}" not in pattern or "{timestamp}" not in pattern:
        raise RenderSnapshotError(
            "file_names.archive_image must contain {scene_name} and {timestamp}"
        )
    name = pattern.replace(
        "{scene_name}", archive_stem(configured_scene_name(config))
    ).replace("{timestamp}", timestamp)
    if "{" in name or "}" in name:
        raise RenderSnapshotError(
            "file_names.archive_image contains an unsupported placeholder"
        )
    _filename(name, "resolved file_names.archive_image")
    if Path(name).suffix != ".png":
        raise RenderSnapshotError("file_names.archive_image must resolve to a PNG filename")
    return name


def _copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise RenderSnapshotError(f"required render input is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _source_files(repository_root: Path, scene_root: Path) -> Iterable[tuple[Path, Path]]:
    """Yield source files and their paths inside the mirrored repository."""

    for pattern in ("*.py", "*.sh"):
        for source in sorted(repository_root.glob(pattern)):
            if source.is_file():
                yield source, Path(source.name)

    for pattern in ("*.py", "*.json", "*.sh"):
        for source in sorted(scene_root.glob(pattern)):
            if source.is_file() and source.name != "config.json":
                yield source, SCENE_DIRECTORY / source.name

    documentation = repository_root / "docs" / "shaft-compositing.md"
    if documentation.is_file():
        yield documentation, Path("docs") / documentation.name

    cpp_root = repository_root / "cpp"
    if cpp_root.is_dir():
        for source in sorted(cpp_root.rglob("*")):
            if source.is_file():
                yield source, source.relative_to(repository_root)


def _validate_config(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise RenderSnapshotError(f"invalid scene configuration {path}: {error}") from error
    if not isinstance(config, dict) or not isinstance(config.get("scene"), dict):
        raise RenderSnapshotError("scene configuration requires a scene object")
    configured_scene_name(config)
    if not isinstance(config.get("camera_settings"), dict):
        raise RenderSnapshotError("scene configuration requires camera_settings")
    if not isinstance(config.get("render_settings"), dict):
        raise RenderSnapshotError("scene configuration requires render_settings")
    file_names = config.get("file_names")
    file_paths = config.get("file_paths")
    if not isinstance(file_names, dict):
        raise RenderSnapshotError("scene configuration requires file_names")
    if not isinstance(file_paths, dict):
        raise RenderSnapshotError("scene configuration requires file_paths")
    _filename(file_names.get("pbrt_scene"), "file_names.pbrt_scene")
    _filename(file_names.get("working_image"), "file_names.working_image")
    scene_files_relative(config)
    resolve_local_archive(config, path.parent.parent)
    remote_archive = file_paths.get("remote_archive")
    if not isinstance(remote_archive, str) or not remote_archive.strip():
        raise RenderSnapshotError("file_paths.remote_archive requires a path")
    pbrt_executable = file_paths.get("pbrt_executable")
    if not isinstance(pbrt_executable, str) or not Path(pbrt_executable).is_absolute():
        raise RenderSnapshotError("file_paths.pbrt_executable requires an absolute path")
    archive_image_name(config, "20000101_000000")
    if "archive" in config:
        raise RenderSnapshotError("obsolete archive root is not supported")
    if "runtime" in config:
        raise RenderSnapshotError("obsolete runtime root is not supported")
    if "pipeline" in config:
        raise RenderSnapshotError("obsolete pipeline root is not supported")
    for name in ("master_file", "output_filename", "generated_medium"):
        if name in config["scene"]:
            raise RenderSnapshotError(f"obsolete scene.{name} is not supported")
    if "camera" in config["scene"]:
        raise RenderSnapshotError("obsolete scene.camera is not supported")
    for name in ("film", "sampler", "integrator"):
        if name in config["scene"]:
            raise RenderSnapshotError(f"obsolete scene.{name} is not supported")
    return config


def create_snapshot(
    repository_root: Path,
    config_path: Path,
    timestamp: str | None = None,
) -> dict[str, str]:
    """Freeze the configuration and render sources in a mirrored repository."""

    repository_root = repository_root.resolve()
    config_path = config_path.resolve()
    scene_root = config_path.parent
    timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    if not TIMESTAMP_PATTERN.fullmatch(timestamp):
        raise RenderSnapshotError(f"invalid render timestamp: {timestamp!r}")

    run_parent = repository_root / RUN_DIRECTORY
    run_parent.mkdir(parents=True, exist_ok=True)
    run_directory = run_parent / timestamp
    try:
        run_directory.mkdir()
    except FileExistsError as error:
        raise RenderSnapshotError(
            f"render snapshot already exists for timestamp {timestamp}"
        ) from error

    snapshot_root = run_directory / "repository"
    snapshot_scene_root = snapshot_root / SCENE_DIRECTORY
    snapshot_config = snapshot_scene_root / "config.json"

    try:
        # The configuration is copied first and all subsequent reads use this
        # copy. Direct edits after this point cannot change the render inputs.
        _copy_file(config_path, snapshot_config)
        config = _validate_config(snapshot_config)

        scene_name = configured_scene_name(config)
        archive_directory = resolve_local_archive(config, repository_root)
        archive_image = archive_image_name(config, timestamp)
        prefix_name = str(Path(archive_image).with_suffix(""))
        if archive_directory.is_dir() and any(
            path.name.startswith(prefix_name) for path in archive_directory.iterdir()
        ):
            raise RenderSnapshotError(
                f"archive output already exists for render {prefix_name}"
            )

        copied_paths = [snapshot_config]
        for source, relative_path in _source_files(repository_root, scene_root):
            destination = snapshot_root / relative_path
            _copy_file(source, destination)
            copied_paths.append(destination)

        cloud_grid = (
            config.get("scene", {})
            .get("sky", {})
            .get("clouds", {})
            .get("grid_builder", {})
        )
        if cloud_grid.get("backend") == "cpp":
            executable_relative = Path(
                cloud_grid.get(
                    "executable", "build/cloud_grid_builder/cloud_grid_builder"
                )
            )
            if executable_relative.is_absolute() or ".." in executable_relative.parts:
                raise RenderSnapshotError(
                    "cloud grid-builder executable must be relative to repository root"
                )
            executable_source = repository_root / executable_relative
            executable_destination = snapshot_root / executable_relative
            if executable_source.is_file():
                _copy_file(executable_source, executable_destination)
                copied_paths.append(executable_destination)
                try:
                    import noise._perlin as native_perlin
                except ModuleNotFoundError as error:
                    if not cloud_grid.get("fallback_to_python", True):
                        raise RenderSnapshotError(
                            "native Python noise library is required by the "
                            "compiled cloud grid builder"
                        ) from error
                else:
                    perlin_source = Path(native_perlin.__file__).resolve()
                    perlin_destination = (
                        snapshot_root / "render_dependencies" / "cloud_perlin.so"
                    )
                    _copy_file(perlin_source, perlin_destination)
                    copied_paths.append(perlin_destination)
            elif not cloud_grid.get("fallback_to_python", True):
                raise RenderSnapshotError(
                    f"required cloud grid-builder executable is missing: "
                    f"{executable_source}"
                )

        relative_scene_files = scene_files_relative(config)

        for path in copied_paths:
            path.chmod(path.stat().st_mode & ~0o222)

        manifest = {
            "snapshot_version": 1,
            "timestamp": timestamp,
            "scene_name": scene_name,
            "source_config": str(config_path),
            "files": {
                str(path.relative_to(snapshot_root)): sha256_file(path)
                for path in sorted(copied_paths)
            },
        }
        manifest_path = run_directory / "input_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest_path.chmod(manifest_path.stat().st_mode & ~0o222)
    except Exception:
        # Preserve a partially created run directory for diagnosis. Never hide
        # the evidence by deleting it automatically.
        raise

    return {
        "timestamp": timestamp,
        "scene_name": scene_name,
        "archive_stem": archive_stem(scene_name),
        "archive_directory": str(archive_directory),
        "archive_image": str(archive_directory / archive_image),
        "run_directory": str(run_directory),
        "repository_root": str(snapshot_root),
        "scene_root": str(snapshot_scene_root),
        "scene_files": str(snapshot_root / relative_scene_files),
        "config": str(snapshot_config),
    }


def _parse_artifact(value: str) -> tuple[str, Path]:
    try:
        suffix, filename = value.split("=", 1)
    except ValueError as error:
        raise RenderSnapshotError(
            "artifact must use SUFFIX=/absolute/or/relative/path syntax"
        ) from error
    if not ARTIFACT_SUFFIX_PATTERN.fullmatch(suffix) or ".." in suffix:
        raise RenderSnapshotError(f"invalid artifact suffix: {suffix!r}")
    return suffix, Path(filename).resolve()


def _tar_filter_for(relative_scene_files: Path):
    """Exclude generated scene output wherever file_paths places it."""

    generated_prefix = ("repository", *relative_scene_files.parts)

    def tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        parts = Path(info.name).parts
        if "__pycache__" in parts:
            return None
        if parts[:len(generated_prefix)] == generated_prefix:
            return None
        return info

    return tar_filter


def finalize_snapshot(
    run_directory: Path,
    archive_prefix: Path,
    artifacts: Iterable[tuple[str, Path]],
) -> Path:
    """Archive the exact frozen inputs and completed render artifacts."""

    run_directory = run_directory.resolve()
    archive_prefix = archive_prefix.resolve()
    snapshot_root = run_directory / "repository"
    snapshot_scene_root = snapshot_root / SCENE_DIRECTORY
    if not snapshot_root.is_dir():
        raise RenderSnapshotError(f"snapshot repository is missing: {snapshot_root}")

    archive_prefix.parent.mkdir(parents=True, exist_ok=True)
    input_manifest_path = run_directory / "input_manifest.json"
    input_manifest = json.loads(input_manifest_path.read_text(encoding="utf-8"))

    compatibility_sources = {
        snapshot_scene_root / "config.json": Path(str(archive_prefix) + "_config.json"),
        snapshot_scene_root / "build_scene.py": Path(
            str(archive_prefix) + "_build_scene.py"
        ),
        snapshot_root / "render_pipeline.sh": Path(
            str(archive_prefix) + "_render_pipeline.sh"
        ),
    }
    for filename in (
        "clouds.py",
        "rain.py",
        "distant_hills.py",
        "vista_surface_texture.py",
        "render_snapshot.py",
        "cloud_grid_contract.py",
    ):
        source = snapshot_root / filename
        if source.is_file():
            compatibility_sources[source] = Path(
                str(archive_prefix) + f"_{filename}"
            )
    frozen_config = _validate_config(snapshot_scene_root / "config.json")
    relative_scene_files = scene_files_relative(frozen_config)
    cloud_jobs = snapshot_root / relative_scene_files / "cloud_grid_jobs"
    if cloud_jobs.is_dir():
        for source in sorted(cloud_jobs.glob("*.json")):
            compatibility_sources[source] = Path(
                str(archive_prefix) + f"_cloud_job_{source.name}"
            )
    for source, destination in compatibility_sources.items():
        _copy_file(source, destination)

    for suffix, source in artifacts:
        if not source.is_file():
            raise RenderSnapshotError(f"completed render artifact is missing: {source}")
        destination = Path(f"{archive_prefix}{suffix}")
        if destination.exists() and destination.resolve() != source:
            raise RenderSnapshotError(f"archive artifact already exists: {destination}")
        if destination.resolve() != source:
            _copy_file(source, destination)

    source_archive = Path(str(archive_prefix) + "_snapshot_sources.tar.gz")
    if source_archive.exists():
        raise RenderSnapshotError(f"snapshot archive already exists: {source_archive}")
    with tarfile.open(source_archive, "w:gz") as archive:
        archive.add(
            snapshot_root,
            arcname="repository",
            filter=_tar_filter_for(relative_scene_files),
        )
        archive.add(input_manifest_path, arcname="input_manifest.json")

    prefix_name = archive_prefix.name
    archived_files = sorted(
        path
        for path in archive_prefix.parent.iterdir()
        if path.is_file()
        and path.name.startswith(prefix_name)
        and not path.name.endswith("_manifest.json")
    )
    final_manifest = {
        **input_manifest,
        "archive_prefix": str(archive_prefix),
        "artifacts": {
            path.name: sha256_file(path)
            for path in archived_files
        },
    }
    final_manifest_path = Path(str(archive_prefix) + "_manifest.json")
    if final_manifest_path.exists():
        raise RenderSnapshotError(f"render manifest already exists: {final_manifest_path}")
    final_manifest_path.write_text(
        json.dumps(final_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return final_manifest_path


def cleanup_snapshot(repository_root: Path, run_directory: Path) -> None:
    """Remove one finalized temporary run directory after strict path checks."""

    repository_root = repository_root.resolve()
    run_directory = run_directory.resolve()
    allowed_parent = (repository_root / RUN_DIRECTORY).resolve()
    if run_directory.parent != allowed_parent or not run_directory.name:
        raise RenderSnapshotError(
            f"refusing to remove non-render workspace: {run_directory}"
        )
    if not (run_directory / "input_manifest.json").is_file():
        raise RenderSnapshotError(
            f"refusing to remove render workspace without manifest: {run_directory}"
        )
    shutil.rmtree(run_directory)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="freeze render inputs")
    create.add_argument("--repository-root", type=Path, required=True)
    create.add_argument("--config", type=Path, required=True)
    create.add_argument("--timestamp")

    finalize = subparsers.add_parser("finalize", help="archive frozen inputs")
    finalize.add_argument("--run-directory", type=Path, required=True)
    finalize.add_argument("--archive-prefix", type=Path, required=True)
    finalize.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="archive artifact as SUFFIX=PATH; repeat as needed",
    )

    cleanup = subparsers.add_parser("cleanup", help="remove a finalized run workspace")
    cleanup.add_argument("--repository-root", type=Path, required=True)
    cleanup.add_argument("--run-directory", type=Path, required=True)
    return parser


def main() -> int:
    arguments = _build_parser().parse_args()
    try:
        if arguments.command == "create":
            result = create_snapshot(
                arguments.repository_root,
                arguments.config,
                arguments.timestamp,
            )
            print(json.dumps(result, sort_keys=True))
        elif arguments.command == "finalize":
            manifest = finalize_snapshot(
                arguments.run_directory,
                arguments.archive_prefix,
                (_parse_artifact(value) for value in arguments.artifact),
            )
            print(manifest)
        else:
            cleanup_snapshot(arguments.repository_root, arguments.run_directory)
    except (OSError, RenderSnapshotError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
