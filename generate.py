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

# Add repo root to path so space_col and foliage are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import space_col
import foliage

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate.py <config.json path>")
        sys.exit(1)

    config_path  = sys.argv[1]
    project_root = os.path.dirname(config_path)

    with open(config_path, 'r') as f:
        cfg = json.load(f)

    scene_cfg = cfg.get('scene', {})

    # --- Space colonization ---
    tree_cfg = scene_cfg.get('tree', {})
    tree     = None

    if tree_cfg.get('enabled', False):
        print(f"  Growing tree: {tree_cfg['num_leaves']} leaves, "
              f"{tree_cfg['max_loops']} max iterations...")
        tree = space_col.Tree3D(tree_cfg)
        tree.grow()
        cylinders = tree.get_cylinders()
        joints    = tree.get_joints()
        space_col.write_tree(tree_cfg, cylinders, joints, project_root)

    # --- Foliage ---
    foliage_cfg = scene_cfg.get('foliage', {})
    if foliage_cfg.get('enabled', False) and tree is not None:
        foliage.run(tree, foliage_cfg, project_root)
    elif foliage_cfg.get('enabled', False) and tree is None:
        print("  WARNING: foliage enabled but tree is disabled — skipping foliage.")

if __name__ == "__main__":
    main()