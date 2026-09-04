"""Dependency-free routing for self-contained atmospheric objects."""


def configured_fog(scene_description):
    """Flatten the single configured fog object for the established writer."""

    fogs = scene_description.get("atmosphere", {}).get("fog", [])
    if not fogs:
        return {"enabled": False}
    if len(fogs) != 1:
        raise ValueError("the current fog generator supports exactly one fog object")
    item = fogs[0]
    boundary = item.get("boundary", {})
    sphere = boundary.get("sphere", {})
    density = item.get("density_field", {})
    medium = item.get("medium", {})
    noise = {key: value for key, value in density.items() if key != "generator"}
    noise["type"] = density.get("generator", "perlin")
    return {
        "enabled": item.get("enabled", False),
        "sigma_a": medium.get("absorption", 0.0),
        "sigma_s": medium.get("scattering", 0.0),
        "g": medium.get("anisotropy", 0.0),
        "camera_inside": boundary.get("camera_inside", True),
        "boundary_center": sphere.get("center", [0.0, 100.0, 0.0]),
        "boundary_radius": sphere.get("radius", 700.0),
        "noise": noise,
    }
