# foliage.py
# Foliage generation — parallel transport frame, phyllotaxis placement,
# leaf venation, leaf mesh, pbrt output.
# Receives Tree3D object directly from generate.py (no serialization).
#
# Sections:
#   1. Imports
#   2. Parallel Transport Frame
#   3. Phyllotaxis Placement
#   4. Leaf Venation (2D space colonization)
#   5. Leaf Mesh Generation
#   6. write_foliage — outputs pbrt Include file
#   7. run — entry point called from generate.py

import os
import math
import random
import numpy as np

# =============================================================================
# 2. Parallel Transport Frame
# =============================================================================

def compute_transport_frames(tree):
    """
    Compute parallel transport frames for all branches.
    Returns dict keyed by id(branch): (T, N, B) as numpy unit vectors.

    The frame minimizes twist along curved branch paths.
    Reference: Runions tree paper, Algorithmic Botany Ch 1.

    T — tangent (branch direction)
    N — normal (perpendicular to T, no twist)
    B — binormal (T x N)
    """
    frames = {}

    # Seed frame at root — use world up [0,1,0] as initial normal
    # unless T is parallel to up, in which case use [1,0,0]
    root = tree.branches[0]
    if len(tree.branches) < 2:
        return frames

    # Get root tangent from first child direction
    child_pos = np.array(tree.branches[1].pos())
    root_pos  = np.array(root.pos())
    T = child_pos - root_pos
    mag = np.linalg.norm(T)
    if mag > 0:
        T /= mag
    else:
        T = np.array([0, 1, 0])

    # Choose initial normal perpendicular to T
    up = np.array([0, 1, 0])
    if abs(np.dot(T, up)) > 0.99:
        up = np.array([1, 0, 0])
    N = np.cross(up, T)
    N /= np.linalg.norm(N)
    B = np.cross(T, N)

    frames[id(root)] = (T.copy(), N.copy(), B.copy())

    # Build children map
    children = {id(b): [] for b in tree.branches}
    for branch in tree.branches:
        if branch.parent is not None:
            children[id(branch.parent)].append(branch)

    # Propagate frames depth-first from root
    stack = [(root, T, N, B)]
    while stack:
        node, T_prev, N_prev, B_prev = stack.pop()
        for child in children[id(node)]:
            cp = np.array(child.pos())
            np_ = np.array(node.pos())
            T_new = cp - np_
            mag = np.linalg.norm(T_new)
            if mag > 0:
                T_new /= mag
            else:
                T_new = T_prev.copy()

            # Parallel transport: project N_prev onto plane perpendicular to T_new
            N_new = N_prev - np.dot(N_prev, T_new) * T_new
            n_mag = np.linalg.norm(N_new)
            if n_mag > 1e-6:
                N_new /= n_mag
            else:
                # Fallback if degenerate
                N_new = np.cross(np.array([0, 1, 0]), T_new)
                n_mag = np.linalg.norm(N_new)
                if n_mag > 1e-6:
                    N_new /= n_mag

            B_new = np.cross(T_new, N_new)

            frames[id(child)] = (T_new.copy(), N_new.copy(), B_new.copy())
            stack.append((child, T_new, N_new, B_new))

    return frames

# =============================================================================
# 3. Phyllotaxis Placement
# =============================================================================

GOLDEN_ANGLE = 137.5077640500378  # degrees — exact value from Fibonacci limit

def compute_phyllotaxis_points(tree, frames, foliage_cfg):
    """
    Walk each branch path from root to tip.
    At each node place a leaf attachment point using cylindrical phyllotaxis.
    Reference: Algorithmic Botany Ch 4, equation 4.2:
        phi = n * 137.5 degrees  (divergence angle)
        H   = h * n              (vertical spacing along branch)

    Returns list of (position, orientation_matrix) tuples.
    position — world space xyz
    orientation_matrix — 3x3 matrix [leaf_right, leaf_up, leaf_normal]
    """
    h            = foliage_cfg.get('internode_distance', 0.3)
    leaf_angle   = foliage_cfg.get('leaf_angle', 45.0)  # degrees from branch axis
    min_loop     = foliage_cfg.get('min_loop_index', 5)  # skip early trunk nodes
    max_radius   = foliage_cfg.get('max_branch_radius', 0.05)  # skip thick branches

    placements = []

    for i, branch in enumerate(tree.branches):
        if branch.loop_index < min_loop:
            continue

        # Skip thick branches — leaves only on fine branches
        branch_radius = tree._radii.get(id(branch), 0.0)
        if branch_radius > max_radius:
            continue

        if id(branch) not in frames:
            continue

        T, N, B = frames[id(branch)]
        pos = np.array(branch.pos())

        # Phyllotaxis rotation around branch tangent T
        n        = branch.loop_index
        phi      = math.radians(n * GOLDEN_ANGLE)
        cos_phi  = math.cos(phi)
        sin_phi  = math.sin(phi)

        # Leaf attachment direction — rotate N around T by phi
        leaf_dir = cos_phi * N + sin_phi * B

        # Tilt leaf away from branch by leaf_angle
        leaf_angle_rad = math.radians(leaf_angle)
        leaf_normal    = (math.cos(leaf_angle_rad) * T +
                         math.sin(leaf_angle_rad) * leaf_dir)
        leaf_normal   /= np.linalg.norm(leaf_normal)

        # Build leaf orientation matrix
        leaf_right = np.cross(leaf_normal, T)
        r_mag = np.linalg.norm(leaf_right)
        if r_mag < 1e-6:
            continue
        leaf_right /= r_mag
        leaf_up = np.cross(leaf_right, leaf_normal)

        placements.append((pos, leaf_right, leaf_up, leaf_normal))

    return placements

# =============================================================================
# 4. Leaf Venation
# =============================================================================

# =============================================================================
# 5. Leaf Mesh Generation (POC — simple disk placeholder)
# =============================================================================

def make_disk_leaf(pos, leaf_right, leaf_up, leaf_normal, scale):
    """
    Generate a simple triangulated disk as a leaf placeholder.
    Returns (points, indices) for a trianglemesh.
    8 triangles, 9 vertices (center + 8 perimeter).
    """
    n_segments = 8
    center = pos
    verts  = [center]

    for i in range(n_segments):
        angle = 2 * math.pi * i / n_segments
        v = (center +
             scale * math.cos(angle) * leaf_right +
             scale * math.sin(angle) * leaf_up)
        verts.append(v)

    indices = []
    for i in range(n_segments):
        i0 = 0
        i1 = i + 1
        i2 = (i + 1) % n_segments + 1
        indices.extend([i0, i1, i2])

    return verts, indices


# =============================================================================
# 6. write_foliage
# =============================================================================

def write_foliage(placements, foliage_cfg, project_root):
    """
    Write scene_files/foliage.pbrt — trianglemesh disks at phyllotaxis points.
    """
    scale    = foliage_cfg.get('leaf_scale', 0.3)
    color    = foliage_cfg.get('leaf_color', [0.15, 0.35, 0.10])
    out_path = os.path.join(project_root, 'scene_files', 'foliage.pbrt')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    lines = ['# foliage.pbrt — generated by foliage.py', '']

    for pos, leaf_right, leaf_up, leaf_normal in placements:
        verts, indices = make_disk_leaf(pos, leaf_right, leaf_up, leaf_normal, scale)

        pts_str = '  '.join(f'{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}' for v in verts)
        idx_str = '  '.join(str(i) for i in indices)

        lines += [
            'AttributeBegin',
            f'    Material "diffuse"  "rgb reflectance" '
            f'[ {color[0]} {color[1]} {color[2]} ]',
            '    Shape "trianglemesh"',
            f'        "integer indices" [ {idx_str} ]',
            f'        "point3 P"        [ {pts_str} ]',
            'AttributeEnd',
            ''
        ]

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"  Written: {out_path}  ({len(placements)} leaves)")
    return 'scene_files/foliage.pbrt'

# =============================================================================
# 7. run
# =============================================================================

def run(tree, foliage_cfg, project_root):
    """
    Entry point called from generate.py.
    Receives live Tree3D object.

    Phase 1: Compute parallel transport frames
    Phase 2: Compute phyllotaxis placement points
    Phase 5: Generate leaf meshes (POC: disk placeholders)
    Phase 6: Write foliage.pbrt
    """
    print("  Computing parallel transport frames...")
    frames = compute_transport_frames(tree)

    print("  Computing phyllotaxis placement...")
    placements = compute_phyllotaxis_points(tree, frames, foliage_cfg)
    print(f"  Leaf placements: {len(placements)}")

    print("  Writing foliage geometry...")
    write_foliage(placements, foliage_cfg, project_root)