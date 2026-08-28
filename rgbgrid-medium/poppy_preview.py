#!/usr/bin/env python3
"""Build a close diagnostic PBRT scene for one procedural poppy."""

import json
from pathlib import Path

from build_scene import _poppy_mesh, _write_detail_mesh


def main():
    output = Path(__file__).parent / "scene_files" / "poppy_preview.pbrt"
    config_path = Path(__file__).parent / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    poppy_config = config["scene"]["terrain"]["details"]["poppies"]
    parts = _poppy_mesh(0, poppy_config)
    lines = [
        '# FILE: poppy_preview.pbrt',
        '# PURPOSE: isolated procedural poppy object study',
        '',
        'LookAt 0.15 2.15 1.65',
        '       0.04 0.54 0.10',
        '       0 1 0',
        'Camera "perspective" "float fov" [ 31 ]',
        'Sampler "zsobol" "integer pixelsamples" [ 512 ]',
        'Integrator "volpath" "integer maxdepth" [ 12 ]',
        'Film "rgb"',
        '    "string filename" [ "poppy_preview.png" ]',
        '    "integer xresolution" [ 1200 ]',
        '    "integer yresolution" [ 1200 ]',
        '',
        'WorldBegin',
        'LightSource "infinite" "rgb L" [ 0.78 0.82 0.88 ] "float scale" [ 0.62 ]',
        '',
        'AttributeBegin',
        '    Material "diffuse" "rgb reflectance" [ 0.10 0.13 0.08 ]',
        '    Shape "trianglemesh"',
        '        "integer indices" [ 0 1 2 0 2 3 ]',
        '        "point3 P" [ -2 0 -2  2 0 -2  2 0 2  -2 0 2 ]',
        'AttributeEnd',
        '',
        'AttributeBegin',
        '    Scale 1.28 1.28 1.28',
        '    Material "diffuse" "rgb reflectance" [ 0.025 0.14 0.018 ]',
    ]
    _write_detail_mesh(lines, *parts["stem"])
    lines.append('    Material "diffuse" "rgb reflectance" [ 0.08 0.21 0.065 ]')
    _write_detail_mesh(lines, *parts["foliage"])
    _write_detail_mesh(lines, *parts["buds"])
    lines += [
        '    TransformBegin',
        '        Scale 0.028 0.070 0.028',
        '        Texture "preview_petal_fiber" "float" "fbm"',
        '            "integer octaves" [ 6 ]',
        '            "float roughness" [ 0.68 ]',
        '    TransformEnd',
        '    Texture "preview_petal_dark" "spectrum" "constant"',
        '        "rgb value" [ 0.46 0.022 0.002 ]',
        '    Texture "preview_petal_light" "spectrum" "constant"',
        '        "rgb value" [ 0.80 0.075 0.008 ]',
        '    Texture "preview_petal_color" "spectrum" "mix"',
        '        "texture tex1" [ "preview_petal_dark" ]',
        '        "texture tex2" [ "preview_petal_light" ]',
        '        "texture amount" [ "preview_petal_fiber" ]',
        '    Material "diffusetransmission"',
        '        "texture reflectance" [ "preview_petal_color" ]',
        '        "rgb transmittance" [ 0.14 0.008 0.001 ]',
    ]
    _write_detail_mesh(lines, *parts["petals"])
    lines.append('    Material "diffuse" "rgb reflectance" [ 0.012 0.003 0.009 ]')
    _write_detail_mesh(lines, *parts["petal_bases"])
    lines += [
        '    Material "diffusetransmission"',
        '        "texture reflectance" [ "preview_petal_color" ]',
        '        "rgb transmittance" [ 0.42 0.028 0.003 ]',
    ]
    _write_detail_mesh(lines, *parts["petal_rims"])
    lines.append('    Material "diffuse" "rgb reflectance" [ 0.008 0.003 0.002 ]')
    _write_detail_mesh(lines, *parts["receptacle"])
    _write_detail_mesh(lines, *parts["filaments"])
    lines.append('    Material "diffuse" "rgb reflectance" [ 0.055 0.010 0.025 ]')
    _write_detail_mesh(lines, *parts["anthers"])
    lines += [
        '    Material "diffuse" "rgb reflectance" [ 0.16 0.30 0.09 ]',
    ]
    _write_detail_mesh(lines, *parts["capsule"])
    lines.append('    Material "diffuse" "rgb reflectance" [ 0.42 0.10 0.12 ]')
    _write_detail_mesh(lines, *parts["stigma"])
    lines += [
        'AttributeEnd',
        '',
    ]
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
