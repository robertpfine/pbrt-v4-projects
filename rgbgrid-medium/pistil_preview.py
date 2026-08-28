#!/usr/bin/env python3
"""Build an isolated, neutrally lit diagnostic scene for the poppy pistil."""

import json
from pathlib import Path

from build_scene import _poppy_mesh, _write_detail_mesh


def main():
    root = Path(__file__).parent
    output = root / "scene_files" / "pistil_preview.pbrt"
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    poppy_config = config["scene"]["terrain"]["details"]["poppies"]
    parts = _poppy_mesh(0, poppy_config)

    lines = [
        '# FILE: pistil_preview.pbrt',
        '# PURPOSE: isolated continuous poppy pistil morphology study',
        '',
        'LookAt 0.006 1.155 0.235',
        '       0.006 1.016 0.173',
        '       0 1 0',
        'Camera "perspective" "float fov" [ 21 ]',
        'Sampler "zsobol" "integer pixelsamples" [ 512 ]',
        'Integrator "path" "integer maxdepth" [ 8 ]',
        'Film "rgb"',
        '    "string filename" [ "pistil_preview.exr" ]',
        '    "integer xresolution" [ 1200 ]',
        '    "integer yresolution" [ 1200 ]',
        '',
        'WorldBegin',
        'LightSource "infinite" "rgb L" [ 0.82 0.84 0.86 ] "float scale" [ 0.75 ]',
        '',
        'AttributeBegin',
        '    Scale 1.28 1.28 1.28',
        '    Material "diffuse" "rgb reflectance" [ 0.38 0.52 0.20 ]',
    ]
    _write_detail_mesh(lines, *parts["capsule"])
    lines.append('    Material "diffuse" "rgb reflectance" [ 0.34 0.055 0.095 ]')
    _write_detail_mesh(lines, *parts["stigma"])
    lines += ['AttributeEnd', '']
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines), encoding='utf-8')
    print(output)


if __name__ == "__main__":
    main()
