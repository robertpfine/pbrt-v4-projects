"""PBRT-native mottled stone color and fine surface bump."""

import math


def validate_stone_texture(config):
    if not isinstance(config, dict):
        return ["texture must be an object"]
    errors = []
    if not isinstance(config.get("enabled", False), bool):
        errors.append("texture.enabled must be boolean")
    if config.get("generator", "granite") != "granite":
        errors.append("texture.generator must be granite")
    for key, default, low, high in (
        ("grain_size", 0.7, 0, None), ("mottle_size", 9.0, 0, None),
        ("grain_strength", 0.7, 0, 1), ("bump_height", 0.12, 0, None),
    ):
        v = config.get(key, default)
        if (not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
                or v < low or (high is not None and v > high)
                or (key.endswith("size") and v == 0)):
            errors.append(f"texture.{key} is outside its valid range")
    for key, default in (("grain_dark", [0.035, 0.032, 0.025]),
                         ("grain_light", [0.60, 0.57, 0.50])):
        color = config.get(key, default)
        if (not isinstance(color, (list, tuple)) or len(color) != 3
                or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                       or not math.isfinite(v) or not 0 <= v <= 1 for v in color)):
            errors.append(f"texture.{key} must contain three reflectances in [0,1]")
    return errors


def write_granite_surface(lines, prefix, config, base_color):
    """Define grain/mottle textures and assign a diffuse, bump-mapped stone."""
    errors = validate_stone_texture(config)
    if errors:
        raise ValueError("; ".join(errors))
    rgb = lambda values: " ".join(f"{v:.9g}" for v in values)
    for label, size, octaves, coefficient in (
        ("grain", config.get("grain_size", 0.7), 1, 0.25),
        ("mottle", config.get("mottle_size", 9.0), 4, 0.125),
    ):
        # PBRT gradient noise is bounded by +/-2. These conservative affine
        # maps keep both mix amounts in [0,1], including all octave weights.
        lines += [
            '    AttributeBegin',
            f'        Scale {size} {size} {size}',
            f'        Texture "{prefix}_{label}_raw" "float" "fbm" '
            f'"integer octaves" [ {octaves} ] "float roughness" [ 0.5 ]',
            '    AttributeEnd',
            f'    Texture "{prefix}_{label}_amount" "float" "mix" '
            f'"float tex1" [ 0.5 ] "float tex2" [ {0.5 + coefficient} ] '
            f'"texture amount" [ "{prefix}_{label}_raw" ]',
        ]
    dark = config.get("grain_dark", [0.035, 0.032, 0.025])
    light = config.get("grain_light", [0.60, 0.57, 0.50])
    lines += [
        f'    Texture "{prefix}_minerals" "spectrum" "mix" '
        f'"rgb tex1" [ {rgb(dark)} ] "rgb tex2" [ {rgb(light)} ] '
        f'"texture amount" [ "{prefix}_grain_amount" ]',
        f'    Texture "{prefix}_base" "spectrum" "mix" '
        f'"rgb tex1" [ {rgb([v * 0.6 for v in base_color])} ] '
        f'"rgb tex2" [ {rgb([min(1.0, v * 1.4) for v in base_color])} ] '
        f'"texture amount" [ "{prefix}_mottle_amount" ]',
        f'    Texture "{prefix}_color" "spectrum" "mix" '
        f'"texture tex1" [ "{prefix}_base" ] "texture tex2" [ "{prefix}_minerals" ] '
        f'"float amount" [ {config.get("grain_strength", 0.7)} ]',
        f'    Texture "{prefix}_bump" "float" "scale" '
        f'"texture tex" [ "{prefix}_grain_raw" ] '
        f'"float scale" [ {config.get("bump_height", 0.12)} ]',
        f'    Material "diffuse" "texture reflectance" [ "{prefix}_color" ] '
        f'"texture displacement" [ "{prefix}_bump" ]',
    ]
