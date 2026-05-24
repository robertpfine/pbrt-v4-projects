# space_col.py
# Space Colonization Algorithm — Runions et al. 2007
# Generates a branching tree structure and outputs pbrt-v4 scene geometry.
#
# Sections:
#   1. Imports
#   2. Leaf3D   — attraction point
#   3. Branch3D — branch node
#   4. Tree3D   — algorithm driver
#   5. write_tree — outputs pbrt Include file
#   6. run       — entry point called from build_scene.py


# =============================================================================
# 1. Imports
# =============================================================================

import os
import math
import random
import json
import numpy as np
from scipy.spatial import KDTree


# =============================================================================
# 2. Leaf3D — attraction point
# =============================================================================

class Leaf3D:
    """
    Attraction point in 3D space.
    Represents available space for branch growth.
    Removed when a branch grows within kill distance.
    """

    __slots__ = ['x', 'y', 'z', 'reached']

    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.reached = False

    def pos(self):
        return (self.x, self.y, self.z)
    

    # =============================================================================
# 3. Branch3D — branch node
# =============================================================================

class Branch3D:
    """
    A node in the branching skeleton.
    Stores position, growth direction, parent pointer, and loop index.
    Growth direction is accumulated from nearby attraction points each
    iteration, then normalized and used to spawn the next branch node.
    """

    __slots__ = ['x', 'y', 'z', 'dir', 'orig_dir', 'parent',
                 'loop_index', 'num_children', 'nearest_leaf_count']

    def __init__(self, x, y, z, direction, loop_index, parent):
        self.x            = x
        self.y            = y
        self.z            = z
        self.dir          = list(direction)   # current growth direction
        self.orig_dir     = list(direction)   # reset target after each iteration
        self.parent       = parent
        self.loop_index   = loop_index
        self.num_children = 0
        self.nearest_leaf_count = 0

    def pos(self):
        return (self.x, self.y, self.z)

    def reset(self):
        """Reset growth direction to original after each iteration."""
        self.dir = list(self.orig_dir)
        self.nearest_leaf_count = 0

    def next(self, growth_dist, loop_index):
        """Spawn and return the next branch node in current growth direction."""
        mag = math.sqrt(self.dir[0]**2 + self.dir[1]**2 + self.dir[2]**2)
        if mag == 0:
            mag = 1.0
        nx = self.x + (self.dir[0] / mag) * growth_dist
        ny = self.y + (self.dir[1] / mag) * growth_dist
        nz = self.z + (self.dir[2] / mag) * growth_dist
        self.num_children += 1
        return Branch3D(nx, ny, nz, self.dir, loop_index, self)
    

    # =============================================================================
# 4. Tree3D — algorithm driver
# =============================================================================

class Tree3D:
    """
    Drives the space colonization algorithm.
    1. Generates attraction points within an ellipsoidal envelope
    2. Grows trunk toward the point cloud
    3. Iteratively branches toward attraction points
    4. Produces cylinder and joint sphere lists for pbrt output
    """

    def __init__(self, cfg):
        self.cfg         = cfg
        D                = cfg['D']
        self.growth_dist = D
        self.min_dist    = cfg['dk'] * D
        self.max_dist    = cfg['di'] * D
        self.max_loops   = cfg['max_loops']
        self.min_leaves  = cfg['min_leaves']
        self.actual_loops = 0

        random.seed(cfg['seed'])

        # Generate attraction points
        self.leaves   = self._generate_leaves()
        
        # Initialize root branch growing upward from configured position
        self.branches = []
        rp = cfg.get('root_position', [0, 0, 0])
        root = Branch3D(rp[0], rp[1], rp[2], [0, 1, 0], 0, None)
        self.branches.append(root)

        # Grow trunk until within max_dist of any leaf
        self._grow_trunk()

    def _generate_leaves(self):
        """
        Generate attraction points within an ellipsoidal envelope
        using Poisson disk (dart throwing) sampling — Runions et al.
        Points are guaranteed to be at least birth_dist apart,
        producing a uniform natural distribution.
        """
        cfg         = self.cfg
        cx, cy, cz  = cfg['point_cloud_center']
        radius      = cfg['point_cloud_radius']
        lw          = cfg['leaf_width']
        lh          = cfg['leaf_height']
        ld          = cfg['leaf_depth']
        target      = cfg['num_leaves']
        birth_dist  = cfg.get('birth_dist', 0.1)
        max_attempts = target * 50

        leaves     = []
        leaf_positions = np.empty((0, 3))  # numpy array for fast distance queries

        attempts = 0
        while len(leaves) < target and attempts < max_attempts:
            attempts += 1

            # Direct ellipsoid sampling — Marsaglia method for unit sphere
            while True:
                u = random.uniform(-1, 1)
                v = random.uniform(-1, 1)
                w = random.uniform(-1, 1)
                if u*u + v*v + w*w <= 1.0:
                    break

            # Scale to ellipsoid and translate to center
            x = cx + u * radius * lw
            y = cy + v * radius * lh
            z = cz + w * radius * ld

            # Poisson disk check — must be at least birth_dist from all existing points
            if len(leaves) > 0:
                dists = np.sqrt(
                    ((leaf_positions[:, 0] - x) ** 2) +
                    ((leaf_positions[:, 1] - y) ** 2) +
                    ((leaf_positions[:, 2] - z) ** 2)
                )
                if np.min(dists) < birth_dist:
                    continue

            leaves.append(Leaf3D(x, y, z))
            leaf_positions = np.vstack([leaf_positions, [x, y, z]]) \
                if len(leaves) > 1 else np.array([[x, y, z]])

        print(f"  Generated {len(leaves)} attraction points "
              f"({attempts} attempts, birth_dist={birth_dist})")
        return leaves
    

    def _grow_trunk(self):
        """
        Grow trunk upward from root until within max_dist of any leaf.
        Matches C++ constructor trunk phase.
        Uses KDTree for efficient nearest-leaf query.
        """
        if not self.leaves:
            return

        # Build numpy array of leaf positions for KDTree
        leaf_positions = np.array([l.pos() for l in self.leaves])
        tree = KDTree(leaf_positions)

        current = self.branches[-1]
        bad_breaker = 100000

        while bad_breaker:
            bad_breaker -= 1

            bx, by, bz = current.pos()

            # Query nearest leaf distance
            dist, _ = tree.query([bx, by, bz])

            if dist < self.max_dist:
                # Trunk has reached the point cloud
                print(f"  Trunk grown: {len(self.branches)} segments")
                return

            # Grow one more trunk segment upward
            new_branch = current.next(self.growth_dist, 0)
            self.branches.append(new_branch)
            current = new_branch

        print("WARNING: trunk growth did not reach point cloud")


    def grow(self):
        """
        Main space colonization loop.
        Each iteration:
          1. For each leaf, find closest branch within radius of influence
          2. Accumulate normalized direction vectors (Runions eq. 2)
          3. Apply tropism bias if configured (Runions eq. 3)
          4. Spawn new branch nodes
          5. Remove reached leaves
          6. Reset branch directions
        """
        cfg          = self.cfg
        min_dist     = self.min_dist
        max_dist     = self.max_dist
        growth_dist  = self.growth_dist
        min_leaves   = self.min_leaves
        max_loops    = self.max_loops

        # Tropism bias vector — optional, from config
        tropism = cfg.get('tropism', None)
        if tropism:
            gx, gy, gz = tropism['x'], tropism['y'], tropism['z']
            tropism_strength = tropism.get('strength', 0.1)

        for iteration in range(max_loops):

            if len(self.leaves) < min_leaves:
                print(f"  Growth complete: {len(self.leaves)} leaves remaining")
                break

            self.actual_loops = iteration

            # Build KDTree of current branch positions
            branch_positions = np.array([b.pos() for b in self.branches])
            kdtree = KDTree(branch_positions)

            # --- Step 1 & 2: find closest branch for each leaf ---
            leaf_positions = np.array([l.pos() for l in self.leaves])

            # Query closest branch for every leaf in one vectorized call
            dists, indices = kdtree.query(leaf_positions)

            for i, leaf in enumerate(self.leaves):
                dist  = dists[i]
                b_idx = indices[i]

                # Kill distance — leaf reached, mark for removal
                if dist < min_dist:
                    leaf.reached = True
                    continue

                # Radius of influence — leaf influences closest branch
                if dist <= max_dist:
                    branch = self.branches[b_idx]
                    lx, ly, lz = leaf.pos()
                    bx, by, bz = branch.pos()

                    # Normalized vector from branch to leaf (Runions eq. 2)
                    dx = lx - bx
                    dy = ly - by
                    dz = lz - bz
                    mag = math.sqrt(dx*dx + dy*dy + dz*dz)
                    if mag > 0:
                        dx /= mag
                        dy /= mag
                        dz /= mag

                    # Accumulate influence
                    branch.dir[0] += dx
                    branch.dir[1] += dy
                    branch.dir[2] += dz
                    branch.nearest_leaf_count += 1

            # --- Step 3 & 4: spawn new branches ---
            new_branches = []
            for branch in self.branches:
                if branch.nearest_leaf_count > 0:
                    # Normalize accumulated direction
                    mag = math.sqrt(
                        branch.dir[0]**2 +
                        branch.dir[1]**2 +
                        branch.dir[2]**2
                    )
                    if mag > 0:
                        branch.dir[0] /= mag
                        branch.dir[1] /= mag
                        branch.dir[2] /= mag

                    # Apply tropism bias (Runions eq. 3)
                    if tropism:
                        tx = branch.dir[0] + gx * tropism_strength
                        ty = branch.dir[1] + gy * tropism_strength
                        tz = branch.dir[2] + gz * tropism_strength
                        tmag = math.sqrt(tx*tx + ty*ty + tz*tz)
                        if tmag > 0:
                            branch.dir[0] = tx / tmag
                            branch.dir[1] = ty / tmag
                            branch.dir[2] = tz / tmag

                    new_branches.append(
                        branch.next(growth_dist, iteration)
                    )

            self.branches.extend(new_branches)

            # --- Step 5: remove reached leaves ---
            self.leaves = [l for l in self.leaves if not l.reached]

            # --- Step 6: reset branch directions ---
            for branch in self.branches:
                branch.reset()

            print(f"  Iteration {iteration+1}: "
                  f"{len(self.branches)} branches, "
                  f"{len(self.leaves)} leaves remaining")
            

    def _compute_murray_radii(self, n=2):
        """
        Compute branch radii using Murray's law, basipetally from tips to root.
        r^n = sum of children r^n
        Tip radius = base_radius from config.
        n=2 gives good results for trees (MacDonald 1983).
        """
        r0 = self.cfg.get('base_radius', 0.015)

        # Build children map
        children = {id(b): [] for b in self.branches}
        for branch in self.branches:
            if branch.parent is not None:
                children[id(branch.parent)].append(branch)

        # Assign radii dict keyed by branch id
        radii = {}

        # Process tips first, then work toward root
        # Use iterative post-order traversal
        stack = [self.branches[0]]  # start at root
        order = []
        visited = set()

        while stack:
            node = stack[-1]
            node_id = id(node)
            kids = children[node_id]
            unvisited_kids = [k for k in kids if id(k) not in visited]
            if unvisited_kids:
                stack.append(unvisited_kids[0])
            else:
                stack.pop()
                order.append(node)
                visited.add(node_id)

        # Assign radii basipetally
        for branch in order:
            node_id = id(branch)
            kids = children[node_id]
            if not kids:
                # Tip node
                radii[node_id] = r0
            else:
                # Murray's law
                radii[node_id] = sum(radii[id(k)]**n for k in kids) ** (1.0/n)

        self._radii = radii
        self._children = children        
            

            
    def get_cylinders(self):
        """
        Returns list of (parent_pos, child_pos, radius) tuples.
        Radius computed using Murray's law via _compute_murray_radii().
        """
        # Compute Murray radii if not already done
        if not hasattr(self, '_radii'):
            self._compute_murray_radii()

        results = []
        for branch in self.branches[1:]:  # skip root
            if branch.parent is None:
                continue
            px, py, pz = branch.parent.pos()
            bx, by, bz = branch.pos()
            radius = self._radii.get(id(branch.parent), self.cfg.get('base_radius', 0.015))
            results.append(((px, py, pz), (bx, by, bz), radius))

        return results

    def get_joints(self):
        """
        Returns list of (pos, radius) tuples for joint spheres.
        Radius matches the cylinder radius at each node.
        """
        if not hasattr(self, '_radii'):
            self._compute_murray_radii()

        results = []
        for branch in self.branches[1:]:
            bx, by, bz = branch.pos()
            radius = self._radii.get(id(branch), self.cfg.get('base_radius', 0.015))
            results.append(((bx, by, bz), radius))

        return results
    


    # =============================================================================
# 5. write_tree — outputs pbrt Include file
# =============================================================================

def write_tree(cfg, cylinders, joints, project_root):
    """
    Writes scene_files/tree.pbrt — an Include file for scene.pbrt.
    Contains cylinders for branch segments and spheres for joints.
    All coordinates scaled from algorithm space to pbrt world space.
    """
    scale     = 1.0
    tx, ty, tz = 0.0, 0.0, 0.0

    trunk_r   = cfg['trunk_material']['reflectance']
    joint_r   = cfg['joint_material']['reflectance']

    out_path  = os.path.join(project_root, 'scene_files', 'tree.pbrt')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    lines = []
    lines.append('# tree.pbrt — generated by space_col.py')
    lines.append('')

    # --- Cylinders ---
    for (px, py, pz), (bx, by, bz), radius in cylinders:
        # Scale and translate to pbrt world space
        px = px * scale + tx
        py = py * scale + ty
        pz = pz * scale + tz
        bx = bx * scale + tx
        by = by * scale + ty
        bz = bz * scale + tz
        r  = radius * scale

        lines.append('AttributeBegin')
        lines.append(f'    Material "diffuse"  '
                     f'"rgb reflectance" [ {trunk_r[0]} {trunk_r[1]} {trunk_r[2]} ]')
        lines.append(f'    # cylinder from ({px:.4f},{py:.4f},{pz:.4f}) '
                     f'to ({bx:.4f},{by:.4f},{bz:.4f})')

        # Cylinder in pbrt is axis-aligned — we need to transform it
        # to align with the branch direction using LookAt-style transform
        dx = bx - px
        dy = by - py
        dz = bz - pz
        length = math.sqrt(dx*dx + dy*dy + dz*dz)

        if length < 1e-6:
            lines.append('AttributeEnd')
            lines.append('')
            continue

        # Translate to parent position, rotate to align with branch direction
        lines.append(f'    Translate {px:.6f} {py:.6f} {pz:.6f}')

        # Compute rotation axis and angle to align +Y with branch direction
        # pbrt cylinder runs along +Z by default — we align to branch vector
        ux, uy, uz = dx/length, dy/length, dz/length

        # Cross product of +Z (0,0,1) with branch direction
        cx_ =  uy
        cy_ = -ux
        cz_ =  0.0
        cross_mag = math.sqrt(cx_*cx_ + cy_*cy_)

        if cross_mag < 1e-6:
            # Branch is already along Z axis
            angle = 0.0 if uz > 0 else 180.0
            lines.append(f'    Rotate {angle:.4f}  1 0 0')
        else:
            angle = math.degrees(math.acos(max(-1.0, min(1.0, uz))))
            lines.append(f'    Rotate {angle:.4f}  '
                         f'{cx_/cross_mag:.6f} {cy_/cross_mag:.6f} 0.0')

        lines.append(f'    Shape "cylinder"  '
                     f'"float radius" [ {r:.6f} ]  '
                     f'"float zmin" [ 0.0 ]  '
                     f'"float zmax" [ {length:.6f} ]')
        lines.append('AttributeEnd')
        lines.append('')

    # --- Joint spheres ---
    for (bx, by, bz), radius in joints:
        bx = bx * scale + tx
        by = by * scale + ty
        bz = bz * scale + tz
        r  = radius * scale

        lines.append('AttributeBegin')
        lines.append(f'    Material "diffuse"  '
                     f'"rgb reflectance" [ {joint_r[0]} {joint_r[1]} {joint_r[2]} ]')
        lines.append(f'    Translate {bx:.6f} {by:.6f} {bz:.6f}')
        lines.append(f'    Shape "sphere"  "float radius" [ {r:.6f} ]')
        lines.append('AttributeEnd')
        lines.append('')

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"  Written: {out_path}")
    print(f"  Cylinders: {len(cylinders)}  Joints: {len(joints)}")

    return 'scene_files/tree.pbrt'



# =============================================================================
# 6. run — entry point called from build_scene.py
# =============================================================================

def run(cfg, project_root):
    """
    Entry point for space colonization tree generation.
    Called from build_scene.py when tree.enabled is true.

    Args:
        cfg          — full scene config dictionary
        project_root — absolute path to project directory

    Returns:
        relative path to tree.pbrt for use as Include directive,
        or None if tree is disabled.
    """
    tree_cfg = cfg.get('scene', {}).get('tree', None)

    if tree_cfg is None or not tree_cfg.get('enabled', False):
        return None

    print(f"  Growing tree: {tree_cfg['num_leaves']} leaves, "
          f"{tree_cfg['max_loops']} max iterations...")

    # Build tree
    tree = Tree3D(tree_cfg)
    tree.grow()

    # Extract geometry
    cylinders = tree.get_cylinders()
    joints    = tree.get_joints()

    # Write pbrt Include file
    return write_tree(tree_cfg, cylinders, joints, project_root)



# =============================================================================
# 7. main — command line entry point
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 space_col.py <config.json path>")
        sys.exit(1)

    config_path  = sys.argv[1]
    project_root = os.path.dirname(config_path)

    with open(config_path, 'r') as f:
        cfg = json.load(f)

    result = run(cfg, project_root)

    if result:
        print(f"  Tree Include file: {result}")
    else:
        print("  Tree disabled in config — nothing to do.")
    




