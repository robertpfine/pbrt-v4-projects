# generate.py
# Procedural geometry orchestrator.
# Called by render_pipeline.sh in place of space_col.py directly.
# Runs space colonization and foliage generation in a single Python process,
# passing the Tree3D object directly to foliage without serialization.
#
# Usage: python3 generate.py <config.json path>

import os
import sys
import json
from pathlib import Path

# Add repo root to path so space_col and foliage are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def configured_space_colonization_trees(cfg):
    """Flatten landform-owned space-colonization construction/population."""

    matches = []
    for landform in cfg.get('scene_description', {}).get('landforms', []):
        for item in landform.get('surface_objects', []):
            if item.get('generator') != 'space_colonization_tree':
                continue
            construction = item.get('construction', {})
            population = item.get('population', {})
            if not isinstance(construction, dict) or not isinstance(population, dict):
                raise ValueError(
                    'space_colonization_tree requires construction and population'
                )
            matches.append({
                'enabled': item.get('enabled', False),
                **construction,
                **population,
            })
    return matches

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate.py <config.json path>")
        sys.exit(1)

    config_path = os.path.abspath(sys.argv[1])

    with open(config_path, 'r') as f:
        cfg = json.load(f)

    repository_root = os.path.dirname(os.path.dirname(config_path))
    scene_files_relative = Path(cfg['file_paths']['scene_files'])
    if (
        scene_files_relative == Path('.')
        or scene_files_relative.is_absolute()
        or '..' in scene_files_relative.parts
    ):
        raise ValueError('file_paths.scene_files must remain inside the repository')
    scene_files_root = os.path.join(repository_root, str(scene_files_relative))

    trees_cfg = configured_space_colonization_trees(cfg)

    import space_col
    import foliage

    for i, tree_cfg in enumerate(trees_cfg):
        if not tree_cfg.get('enabled', False):
            print(f"  Tree {i}: disabled, skipping.")
            continue

        print(f"  Growing tree {i}: {tree_cfg['num_leaves']} leaves, "
              f"{tree_cfg['max_loops']} max iterations, seed {tree_cfg['seed']}...")

        # --- Space colonization ---
        tree = space_col.Tree3D(tree_cfg)
        tree.grow()
        cylinders = tree.get_cylinders()
        joints    = tree.get_joints()
        space_col.write_tree(
            tree_cfg, cylinders, joints, scene_files_root, index=i
        )

        # --- Foliage ---
        foliage_cfg = tree_cfg.get('foliage', {})
        if foliage_cfg.get('enabled', False):
            foliage.run(tree, foliage_cfg, scene_files_root, index=i)
        else:
            print(f"  Tree {i}: foliage disabled, skipping.")

if __name__ == "__main__":
    main()
