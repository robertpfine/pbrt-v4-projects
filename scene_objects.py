"""Dependency-free routing for independent scene objects."""


def configured_rgbgrid_media(scene_description):
    """Return enabled independent objects that own an rgbgrid medium."""

    result = []
    for item in scene_description.get("objects", []):
        medium = item.get("medium", {})
        interior = medium.get("interior", {}) if isinstance(medium, dict) else {}
        if interior.get("type") == "rgbgrid" and item.get("enabled", False):
            result.append(interior)
    return result


def configured_scene_objects(scene_description, generator):
    """Flatten independent objects registered to one generator family."""

    result = []
    for item in scene_description.get("objects", []):
        geometry = item.get("geometry", {})
        if not isinstance(geometry, dict) or geometry.get("generator") != generator:
            continue
        construction = item.get("construction", {})
        if not isinstance(construction, dict):
            raise ValueError(
                f"scene object {item.get('name')!r} requires a construction object"
            )
        result.append({
            "enabled": item.get("enabled", False),
            "label": item.get("name", generator),
            "_placement": item.get("placement", {}),
            **construction,
        })
    return result


def configured_independent_geometry(scene_description):
    """Adapt independent native/box objects to the established writer."""

    result = []
    for item in scene_description.get("objects", []):
        geometry = item.get("geometry", {})
        medium = item.get("medium")
        if not isinstance(geometry, dict) or not isinstance(medium, dict):
            continue
        if geometry.get("pbrt_shape") == "sphere":
            shape = {"type": "sphere", **geometry.get("parameters", {})}
        elif geometry.get("generator") == "box":
            shape = {"type": "box", **item.get("construction", {})}
        else:
            continue
        placement = item.get("placement", {})
        rotations = []
        for angle, axis in zip(
            placement.get("rotation_degrees", [0.0, 0.0, 0.0]),
            ([1, 0, 0], [0, 1, 0], [0, 0, 1]),
        ):
            if angle != 0:
                rotations.append({"angle": angle, "axis": axis})
        interior = medium.get("interior", {})
        result.append({
            "enabled": item.get("enabled", False),
            "label": item.get("name", "independent_object"),
            "material": item.get("material", {"type": "interface"}),
            "medium_interior": interior.get("name", ""),
            "medium_exterior": medium.get("exterior", ""),
            "transform": {
                "translate": placement.get("position", [0.0, 0.0, 0.0]),
                "rotate": rotations,
            },
            "shape": shape,
        })
    return result
