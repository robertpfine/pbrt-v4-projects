"""Whole-plant instancing built from the original sunflower phyllotaxis writer."""

from copy import deepcopy
import math
import re

from terrain_details import scatter_points


def validate_sunflower(construction, population):
    """Validate field controls before allocating geometry or writing a scene."""
    errors = []

    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    def pair(value, positive=False):
        return (isinstance(value, list) and len(value) == 2
                and all(number(v) for v in value) and value[0] <= value[1]
                and (not positive or value[0] > 0))

    variants = construction.get("variants", 1)
    if type(variants) is not int or not 1 <= variants <= 32:
        errors.append("construction.variants must be an integer in [1, 32]")
    for key in ("head_pitch_variation", "stem_length_variation"):
        value = construction.get(key, 0)
        if not number(value) or value < 0 or (key == "stem_length_variation" and value >= 1):
            errors.append(f"construction.{key} must be nonnegative (stem variation < 1)")
    pattern = construction.get("pattern")
    if not isinstance(pattern, dict):
        errors.append("construction.pattern must contain the sunflower head recipe")
    else:
        if type(pattern.get("count")) is not int or pattern["count"] <= 0:
            errors.append("construction.pattern.count must be positive")
        center = pattern.get("center")
        if not isinstance(center, list) or len(center) != 3 or not all(number(v) for v in center):
            errors.append("construction.pattern.center must contain three finite numbers")
        support = pattern.get("support", {})
        if not isinstance(support, dict):
            support = {}
        stem = support.get("stem", {})
        if not isinstance(stem, dict):
            stem = {}
        if not support.get("enabled") or not stem.get("enabled"):
            errors.append("construction.pattern.support and its stem must be enabled")
        for key in ("length", "base_radius", "tip_radius"):
            if not number(stem.get(key)) or stem[key] <= 0:
                errors.append(f"construction.pattern.support.stem.{key} must be positive")
        if type(stem.get("segments")) is not int or stem["segments"] < 1:
            errors.append("construction.pattern.support.stem.segments must be positive")
        for key in ("top_offset_y", "top_offset_z", "sway"):
            if not number(stem.get(key, 0)):
                errors.append(f"construction.pattern.support.stem.{key} must be finite")
        if not number(pattern.get("head_pitch", 85)):
            errors.append("construction.pattern.head_pitch must be finite")
    if population.get("method") not in {"scatter", "explicit"}:
        errors.append("population.method must be scatter or explicit")
    if not pair(population.get("scale", [1, 1]), positive=True):
        errors.append("population.scale must be an ascending positive pair")
    for key in ("heading_degrees", "heading_spread_degrees", "y_offset"):
        if not number(population.get(key, 0)):
            errors.append(f"population.{key} must be finite")
    spread = population.get("heading_spread_degrees", 180)
    if number(spread) and not 0 <= spread <= 180:
        errors.append("population.heading_spread_degrees must be in [0, 180]")
    if population.get("method") == "scatter":
        if type(population.get("count")) is not int or population["count"] < 0:
            errors.append("population.count must be a nonnegative integer")
        region = population.get("region", {})
        if not isinstance(region, dict):
            region = {}
        for key in ("center", "size"):
            value = region.get(key)
            if (not isinstance(value, list) or len(value) != 2
                    or not all(number(v) for v in value)
                    or (key == "size" and min(value) <= 0)):
                errors.append(f"population.region.{key} must contain two finite numbers (size > 0)")
        if type(population.get("seed", 1)) is not int:
            errors.append("population.seed must be an integer")
        slope = population.get("max_slope_degrees", 90)
        if not number(slope) or not 0 <= slope <= 90:
            errors.append("population.max_slope_degrees must be in [0, 90]")
    else:
        instances = population.get("instances", [])
        if not isinstance(instances, list):
            errors.append("population.instances must be a list")
        else:
            for i, instance in enumerate(instances):
                if not isinstance(instance, dict):
                    errors.append(f"population.instances.{i} must be an object")
                    continue
                position = instance.get("position")
                if not isinstance(position, list) or len(position) != 3 or not all(number(v) for v in position):
                    errors.append(f"population.instances.{i}.position must contain three finite numbers")
                if not number(instance.get("scale", 1)) or instance.get("scale", 1) <= 0:
                    errors.append(f"population.instances.{i}.scale must be positive")
                if not number(instance.get("rotation_degrees", 0)):
                    errors.append(f"population.instances.{i}.rotation_degrees must be finite")
                variant = instance.get("variant", 0)
                if type(variant) is not int or type(variants) is not int or not 0 <= variant < variants:
                    errors.append(f"population.instances.{i}.variant is out of range")
    return errors


def expand_organs(lines):
    """Expand the legacy writer's organ objects for a legal PBRT plant prototype.

    This consumes generated declarations only, not arbitrary PBRT input. PBRT-v4
    forbids ObjectInstance inside ObjectBegin. Preserve each organ's transforms
    and materials, expanding definitions once per plant variant, not per plant.
    """
    definitions = {}
    output = []
    current = None
    for line in lines:
        begin = re.fullmatch(r'\s*ObjectBegin "([^"]+)"\s*', line)
        instance = re.fullmatch(r'\s*ObjectInstance "([^"]+)"\s*', line)
        if begin:
            if current is not None:
                raise ValueError("nested sunflower organ definition")
            current = begin[1]
            definitions[current] = []
        elif line.strip() == "ObjectEnd":
            if current is None:
                raise ValueError("unmatched sunflower ObjectEnd")
            current = None
        elif instance:
            if current is not None or instance[1] not in definitions:
                raise ValueError("unresolved or nested sunflower organ instance")
            output.extend(["AttributeBegin", *definitions[instance[1]], "AttributeEnd"])
        elif current is not None:
            definitions[current].append(line)
        else:
            output.append(line)
    if current is not None:
        raise ValueError("unterminated sunflower organ definition")
    return output


def write_sunflower_field(lines, terrain, entry, prefix, head_writer, camera=None, film=None):
    if not entry.get("enabled", False):
        return
    construction, population = entry["construction"], entry["population"]
    errors = validate_sunflower(construction, population)
    if errors:
        raise ValueError("sunflower: " + "; ".join(errors))
    variants = construction.get("variants", 1)
    for variant in range(variants):
        pattern = deepcopy(construction["pattern"])
        fraction = 0 if variants == 1 else 2 * variant / (variants - 1) - 1
        pattern["enabled"] = True
        pattern.pop("_placement", None)
        pattern["head_pitch"] = pattern.get("head_pitch", 85) + fraction * construction.get("head_pitch_variation", 0)
        stem = pattern["support"]["stem"]
        stem["length"] *= 1 + fraction * construction.get("stem_length_variation", 0)
        center = pattern["center"]
        root_y = center[1] + stem.get("top_offset_y", -3) - stem["length"]
        organs = []
        head_writer(organs, [pattern])
        lines.extend([
            f'ObjectBegin "{prefix}_{variant}"',
            "AttributeBegin",
            f'Translate {-center[0]} {-root_y} {-center[2]}',
            *expand_organs(organs),
            "AttributeEnd", "ObjectEnd",
        ])
    if population["method"] == "scatter":
        points = scatter_points(terrain, {**population, "enabled": True, "variants": variants},
                                camera=camera, film=film)
        if len(points) != population["count"]:
            raise ValueError(f"sunflower scatter accepted {len(points)} of {population['count']} requested plants")
        placements = [(p.position, p.scale, p.variant,
                       population.get("heading_degrees", 0)
                       + (p.rotation / 180 - 1) * population.get("heading_spread_degrees", 180))
                      for p in points]
    else:
        placements = []
        for item in population.get("instances", []):
            x, y, z = item["position"]
            if not terrain.x_min <= x <= terrain.x_max or not terrain.z_min <= z <= terrain.z_max:
                raise ValueError("explicit sunflower lies outside its landform")
            y += terrain.sample(x, z).height + population.get("y_offset", 0)
            placements.append(((x, y, z), item.get("scale", 1), item.get("variant", 0),
                               item.get("rotation_degrees", 0)))
    lines.append(f'# Sunflower field {prefix}: {len(placements)} whole-plant instances')
    for (x, y, z), scale, variant, heading in placements:
        lines.extend(["AttributeBegin", f"Translate {x} {y} {z}",
                      f"Rotate {heading} 0 1 0", f"Scale {scale} {scale} {scale}",
                      f'ObjectInstance "{prefix}_{variant}"', "AttributeEnd"])
