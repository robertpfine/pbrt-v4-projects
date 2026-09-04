#!/usr/bin/env python3
"""Compact short scalar arrays without otherwise rewriting scene JSON."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import tempfile


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "scene_workspace" / "config.json"


class SceneConfigFormatError(ValueError):
    """Raised when source text cannot be formatted without changing its data."""


def _array_ranges(source: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    stack: list[int] = []
    in_string = False
    escaped = False

    for index, character in enumerate(source):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "[":
            stack.append(index)
        elif character == "]":
            if not stack:
                raise SceneConfigFormatError("unmatched closing array bracket")
            ranges.append((stack.pop(), index + 1))

    if in_string:
        raise SceneConfigFormatError("unterminated JSON string")
    if stack:
        raise SceneConfigFormatError("unmatched opening array bracket")
    return ranges


def _split_scalar_elements(interior: str) -> list[str]:
    if not interior.strip():
        return []

    elements: list[str] = []
    start = 0
    in_string = False
    escaped = False
    for index, character in enumerate(interior):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
        elif character == '"':
            in_string = True
        elif character == ",":
            elements.append(interior[start:index].strip())
            start = index + 1
    elements.append(interior[start:].strip())
    return elements


def compact_short_scalar_arrays(
    source: str,
    *,
    max_items: int = 4,
    max_inline_width: int = 120,
) -> str:
    """Return JSON with only short, scalar arrays collapsed onto one line."""
    try:
        original_data = json.loads(source)
    except json.JSONDecodeError as error:
        raise SceneConfigFormatError(f"invalid input JSON: {error}") from error

    replacements: list[tuple[int, int, str]] = []
    for start, end in _array_ranges(source):
        candidate = source[start:end]
        if "\n" not in candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, list) or len(value) > max_items:
            continue
        if any(isinstance(item, (list, dict)) for item in value):
            continue

        elements = _split_scalar_elements(candidate[1:-1])
        compact = "[" + ", ".join(elements) + "]"
        if len(compact) > max_inline_width:
            continue
        replacements.append((start, end, compact))

    result = source
    for start, end, compact in sorted(replacements, reverse=True):
        result = result[:start] + compact + result[end:]

    try:
        formatted_data = json.loads(result)
    except json.JSONDecodeError as error:
        raise SceneConfigFormatError(f"formatter produced invalid JSON: {error}") from error
    if formatted_data != original_data:
        raise SceneConfigFormatError("formatter changed parsed configuration data")
    return result


def format_file(path: Path, *, check: bool = False) -> bool:
    source = path.read_text(encoding="utf-8")
    formatted = compact_short_scalar_arrays(source)
    changed = formatted != source
    if check or not changed:
        return changed

    original_mode = stat.S_IMODE(path.stat().st_mode)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(formatted)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, original_mode)
        os.replace(temporary_name, path)
    except OSError:
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
        raise
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report whether formatting is needed without writing",
    )
    arguments = parser.parse_args()

    changed = format_file(arguments.path, check=arguments.check)
    if arguments.check:
        if changed:
            print(f"needs formatting: {arguments.path}")
            return 1
        print(f"formatting current: {arguments.path}")
        return 0
    print(f"{'formatted' if changed else 'unchanged'}: {arguments.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
