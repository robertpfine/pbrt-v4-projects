#!/usr/bin/env python3
"""Build a close diagnostic PBRT scene for one procedural poppy."""

from pathlib import Path

from build_scene import _poppy_mesh, _write_detail_mesh


def main():
    output = Path(__file__).parent / "scene_files" / "poppy_preview.pbrt"
    parts = _poppy_mesh(0)
    lines = [
        '# FILE: poppy_preview.pbrt',
        '# PURPOSE: isolated procedural poppy object study',
        '',
        'LookAt 0 1.62 0.82',
        '       0 1.08 0',
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
        'LightSource "infinite" "rgb L" [ 0.42 0.48 0.58 ] "float scale" [ 0.34 ]',
        'LightSource "distant" "point3 from" [ -3 5 4 ] "point3 to" [ 0 0.7 0 ]',
        '    "blackbody L" [ 4700 ] "float scale" [ 3.2 ]',
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
    lines += [
        '    Material "diffusetransmission"',
        '        "texture reflectance" [ "preview_petal_color" ]',
        '        "rgb transmittance" [ 0.42 0.028 0.003 ]',
    ]
    _write_detail_mesh(lines, *parts["petal_rims"])
    lines.append('    Material "diffuse" "rgb reflectance" [ 0.008 0.003 0.002 ]')
    _write_detail_mesh(lines, *parts["stamens"])
    lines += [
        '    Material "diffuse" "rgb reflectance" [ 0.38 0.46 0.13 ]',
    ]
    _write_detail_mesh(lines, *parts["capsule"])
    lines += [
        'AttributeEnd',
        '',
    ]
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
