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
from pathlib import Path
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
        """Clear the attraction-direction accumulator for the next iteration."""
        self.dir = [0.0, 0.0, 0.0]
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


def decimate_branches(branches, minimum_spacing):
    """Decimate each branch using accumulated distance from base to tip."""
    if minimum_spacing <= 0.0:
        raise ValueError("decimation minimum spacing must be greater than zero")

    children = {id(branch): [] for branch in branches}
    for branch in branches:
        if branch.parent is not None:
            children[id(branch.parent)].append(branch)

    retained_ids = {id(branches[0])}

    def process_branch(base, first_node):
        """Process one maximal path from a root or fork toward its next endpoint."""
        accumulated_distance = 0.0
        previous = base
        node = first_node

        while True:
            accumulated_distance += math.dist(previous.pos(), node.pos())
            kids = children[id(node)]
            is_endpoint = len(kids) != 1

            if accumulated_distance >= minimum_spacing or is_endpoint:
                retained_ids.add(id(node))
                accumulated_distance = 0.0

            if is_endpoint:
                for child in kids:
                    process_branch(node, child)
                return

            previous = node
            node = kids[0]

    for child in children[id(branches[0])]:
        process_branch(branches[0], child)

    return [branch for branch in branches if id(branch) in retained_ids]


def subdivide_polyline(samples, iterations, corner_cut_ratio):
    """Apply open-curve corner cutting while preserving both endpoints."""
    if iterations < 0 or not isinstance(iterations, int):
        raise ValueError("subdivision iterations must be a non-negative integer")
    if not 0.0 < corner_cut_ratio < 0.5:
        raise ValueError("subdivision corner_cut_ratio must be between 0 and 0.5")

    result = samples
    for _ in range(iterations):
        if len(result) < 3:
            break

        refined = [result[0]]
        for (p0, r0), (p1, r1) in zip(result, result[1:]):
            q_position = (1.0 - corner_cut_ratio) * p0 + corner_cut_ratio * p1
            q_radius = (1.0 - corner_cut_ratio) * r0 + corner_cut_ratio * r1
            r_position = corner_cut_ratio * p0 + (1.0 - corner_cut_ratio) * p1
            r_radius = corner_cut_ratio * r0 + (1.0 - corner_cut_ratio) * r1
            refined.extend(((q_position, q_radius), (r_position, r_radius)))
        refined.append(result[-1])
        result = refined

    return result
    

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
        self.min_dist    = cfg['dk_multiplier'] * D
        di_multiplier    = cfg['di_multiplier']
        self.max_dist    = math.inf if di_multiplier is None else di_multiplier * D
        self.max_loops   = cfg['max_loops']
        self.min_leaves  = cfg['min_leaves']
        self.actual_loops = 0

        random.seed(cfg['seed'])

        # Generate attraction points
        self.leaves   = self._generate_leaves()
        self.leaves_initial = len(self.leaves)
        
        # Initialize root branch growing upward from configured position
        self.branches = []
        rp = cfg.get('root_position', [0, 0, 0])
        root = Branch3D(rp[0], rp[1], rp[2], [0, 1, 0], 0, None)
        self.branches.append(root)

        # Optional prescribed trunk below the attraction field. This is
        # independent of di, so it also works when the radius of influence
        # is infinite.
        initial_trunk_length = cfg.get('initial_trunk_length', 0.0)
        if initial_trunk_length < 0.0:
            raise ValueError("initial_trunk_length must be non-negative")
        trunk_form_cfg = cfg.get('trunk_form', {})
        sway_amplitude = trunk_form_cfg.get('sway_amplitude', 0.0)
        sway_cycles = trunk_form_cfg.get('sway_cycles', 0.75)
        if sway_amplitude < 0.0:
            raise ValueError("trunk_form sway_amplitude must be non-negative")
        if sway_cycles <= 0.0:
            raise ValueError("trunk_form sway_cycles must be positive")
        trunk_segment_count = (
            math.ceil(initial_trunk_length / self.growth_dist)
            if initial_trunk_length > 0.0 else 0
        )
        root.loop_index = -trunk_segment_count
        remaining_trunk = initial_trunk_length
        current = root
        trunk_segment_index = 0
        while remaining_trunk > 1e-12:
            segment_length = min(self.growth_dist, remaining_trunk)
            trunk_segment_index += 1
            current = current.next(
                segment_length,
                -trunk_segment_count + trunk_segment_index
            )
            self.branches.append(current)
            remaining_trunk -= segment_length
        self._prescribed_trunk_ids = {
            id(branch) for branch in self.branches
        }
        self._initial_trunk_length = initial_trunk_length
        if initial_trunk_length > 0.0:
            print(f"  Prescribed trunk: {initial_trunk_length:.3f} "
                  f"({len(self.branches) - 1} segments)")

        # Grow trunk until within max_dist of any leaf
        self._grow_trunk()

    def _point_inside_crown(self, x, y, z):
        """
        Return True if an attraction point is allowed inside the crown volume.
        """

        cfg = self.cfg

        _, cy, _ = cfg['point_cloud_center']
        radius = cfg['point_cloud_radius']

        lower_fraction = cfg.get('lower_crown_fraction', 0.0)
        lower_y = cy - lower_fraction * radius

        return y >= lower_y    

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

            if not self._point_inside_crown(x, y, z):
                continue

            

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
    


    def _inject_attraction_points(self, iteration, ca_cfg):
        """
        Inject new attraction points into the cloud during growth.

        Implements the Figure 8 idea from Runions et al.:
        new attraction points are continuously added while the
        minimum spacing between points gradually decreases.

        Important:
        Every newly accepted point is also included in the spacing
        test for subsequent candidates in the same injection pass.
        """

        cfg                   = self.cfg
        cx, cy, cz            = cfg['point_cloud_center']
        radius                = cfg['point_cloud_radius']
        lw                    = cfg['leaf_width']
        lh                    = cfg['leaf_height']
        ld                    = cfg['leaf_depth']

        points_per_iter       = ca_cfg.get('points_per_iteration', 100)
        initial_birth_dist    = ca_cfg.get('initial_birth_dist', 2.0)
        final_birth_dist      = ca_cfg.get('final_birth_dist', 0.5)
        iters_to_full_density = ca_cfg.get('iterations_to_full_density', 100)
        exclude_near_tree     = ca_cfg.get('exclude_near_tree', False)
        infill_cfg             = ca_cfg.get('infill', {})
        infill_active          = (
            infill_cfg.get('enabled', False)
            and iteration >= infill_cfg.get('start_iteration', 0)
        )
        infill_min_dist        = (
            infill_cfg.get('min_tree_distance_multiplier', 0.0)
            * self.growth_dist
        )
        infill_max_dist        = (
            infill_cfg.get('max_tree_distance_multiplier', 20.0)
            * self.growth_dist
        )
        if infill_active:
            if infill_min_dist < self.min_dist:
                raise ValueError(
                    "continuous_attraction infill minimum tree distance "
                    "must be at least dk"
                )
            if infill_max_dist <= infill_min_dist:
                raise ValueError(
                    "continuous_attraction infill maximum tree distance "
                    "must exceed its minimum tree distance"
                )

            if not hasattr(self, '_infill_bounds'):
                crown_positions = np.array(
                    [
                        branch.pos() for branch in self.branches
                        if id(branch) not in self._prescribed_trunk_ids
                    ],
                    dtype=float
                )
                if len(crown_positions) == 0:
                    raise ValueError(
                        "continuous_attraction infill requires crown branches"
                    )
                self._infill_bounds = (
                    np.min(crown_positions, axis=0),
                    np.max(crown_positions, axis=0)
                )

                crown_tree = KDTree(crown_positions)
                retained_leaves = []
                for leaf in self.leaves:
                    candidate = np.asarray(leaf.pos(), dtype=float)
                    inside_bounds = np.all(
                        candidate >= self._infill_bounds[0]
                    ) and np.all(candidate <= self._infill_bounds[1])
                    if not inside_bounds:
                        continue
                    distance_to_tree, _ = crown_tree.query(candidate)
                    if infill_min_dist <= distance_to_tree <= infill_max_dist:
                        retained_leaves.append(leaf)

                removed = len(self.leaves) - len(retained_leaves)
                self.leaves = retained_leaves
                print(
                    f"  Infill activated at iteration {iteration + 1}: "
                    f"froze crown bounds and removed {removed} frontier points"
                )

        # Gradually reduce the minimum spacing between attraction points.
        t = min(1.0, iteration / max(1, iters_to_full_density))
        birth_dist = (
            initial_birth_dist
            + t * (final_birth_dist - initial_birth_dist)
        )

        # Positions of all currently existing attraction points.
        if self.leaves:
            existing_positions = np.array(
                [leaf.pos() for leaf in self.leaves],
                dtype=float
            )
        else:
            existing_positions = np.empty((0, 3), dtype=float)

        branch_tree = None
        if exclude_near_tree or infill_active:
            branch_positions = np.array(
                [
                    branch.pos() for branch in self.branches
                    if not infill_active
                    or id(branch) not in self._prescribed_trunk_ids
                ],
                dtype=float
            )
            branch_tree = KDTree(branch_positions)

        # Keep newly accepted points separately so that candidates are
        # checked against points added earlier in THIS SAME iteration.
        new_positions = []

        injected = 0
        attempts = 0
        attempt_multiplier = (
            infill_cfg.get('attempts_per_point', 200)
            if infill_active else 50
        )
        max_attempts = points_per_iter * attempt_multiplier

        while injected < points_per_iter and attempts < max_attempts:
            attempts += 1

            if infill_active:
                lower, upper = self._infill_bounds
                x = random.uniform(lower[0], upper[0])
                y = random.uniform(lower[1], upper[1])
                z = random.uniform(lower[2], upper[2])
            else:
                # Random point inside unit sphere.
                while True:
                    u = random.uniform(-1.0, 1.0)
                    v = random.uniform(-1.0, 1.0)
                    w = random.uniform(-1.0, 1.0)

                    if u*u + v*v + w*w <= 1.0:
                        break

                # Transform unit sphere into configured ellipsoid.
                x = cx + u * radius * lw
                y = cy + v * radius * lh
                z = cz + w * radius * ld

                if not self._point_inside_crown(x, y, z):
                    continue

            

            candidate = np.array([x, y, z], dtype=float)

            if branch_tree is not None:
                distance_to_tree, _ = branch_tree.query(candidate)
                minimum_tree_distance = (
                    infill_min_dist if infill_active else self.min_dist
                )
                if distance_to_tree < minimum_tree_distance:
                    continue
                if infill_active and distance_to_tree > infill_max_dist:
                    continue

            # Check against attraction points that existed before
            # this injection pass.
            if len(existing_positions) > 0:
                distances = np.linalg.norm(
                    existing_positions - candidate,
                    axis=1
                )

                if np.min(distances) < birth_dist:
                    continue

            # ALSO check against points already accepted during
            # this same injection pass.
            if new_positions:
                new_array = np.array(new_positions)

                distances = np.linalg.norm(
                    new_array - candidate,
                    axis=1
                )

                if np.min(distances) < birth_dist:
                    continue

            # Candidate satisfies the current spacing requirement.
            self.leaves.append(Leaf3D(x, y, z))
            new_positions.append(candidate)

            injected += 1

        print(
            f"  Injected {injected} attraction points "
            f"(birth_dist={birth_dist:.3f}, attempts={attempts}, "
            f"mode={'infill' if infill_active else 'envelope'})"
        )

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

        direction_persistence = cfg.get('direction_persistence', {})
        persistence_strength = (
            direction_persistence.get('strength', 0.0)
            if direction_persistence.get('enabled', False)
            else 0.0
        )

        topology_cfg = cfg.get('topology', {})
        max_children_per_node = topology_cfg.get('max_children_per_node')
        if max_children_per_node is not None:
            if not isinstance(max_children_per_node, int) or max_children_per_node < 1:
                raise ValueError(
                    "topology max_children_per_node must be a positive integer"
                )

        prev_leaf_count = len(self.leaves)
        stuck_iterations = 0
        max_stuck = 5

        # Equation 2 uses only the attraction vectors from the current iteration.
        # Clear the directions inherited from trunk construction.
        for branch in self.branches:
            branch.reset()

        for iteration in range(max_loops):

            # Inject new attraction points if continuous addition enabled
            ca_cfg = self.cfg.get('continuous_attraction', {})
            if ca_cfg.get('enabled', False):
                self._inject_attraction_points(iteration, ca_cfg)

            if len(self.leaves) < min_leaves:
                print(f"  Growth complete: {len(self.leaves)} leaves remaining")
                break

            if len(self.leaves) == prev_leaf_count and len(self.leaves) < self.leaves_initial:
                stuck_iterations += 1
                if stuck_iterations >= max_stuck:
                    print(f"  Growth stalled: {len(self.leaves)} leaves unreachable, stopping.")
                    break
            else:
                stuck_iterations = 0
                prev_leaf_count = len(self.leaves)

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
                #if dist < min_dist:
                #    leaf.reached = True
                #    continue

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
                    # Experimental topology constraint: prevent a single node
                    # from repeatedly originating many branches over time.
                    if (max_children_per_node is not None
                            and branch.num_children >= max_children_per_node):
                        continue

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

                    # Experimental directional persistence: bias growth toward
                    # the direction of the segment entering this branch node.
                    if persistence_strength > 0.0:
                        px = branch.dir[0] + branch.orig_dir[0] * persistence_strength
                        py = branch.dir[1] + branch.orig_dir[1] * persistence_strength
                        pz = branch.dir[2] + branch.orig_dir[2] * persistence_strength
                        pmag = math.sqrt(px*px + py*py + pz*pz)
                        if pmag > 0:
                            branch.dir[0] = px / pmag
                            branch.dir[1] = py / pmag
                            branch.dir[2] = pz / pmag

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

            

            # --- Step 5: remove attraction points reached by the newly grown tree ---

            if self.leaves:
                branch_positions = np.array([b.pos() for b in self.branches])
                branch_tree = KDTree(branch_positions)

                leaf_positions = np.array([l.pos() for l in self.leaves])

                dists, _ = branch_tree.query(leaf_positions)

                for i, leaf in enumerate(self.leaves):
                    if dists[i] < min_dist:
                        leaf.reached = True

            self.leaves = [l for l in self.leaves if not l.reached]

            # --- Step 6: reset branch directions ---
            for branch in self.branches:
                branch.reset()

            print(f"  Iteration {iteration+1}: "
                  f"{len(self.branches)} branches, "
                  f"{len(self.leaves)} leaves remaining")
            

    def _compute_murray_radii(self):
        """
        Compute branch radii using Murray's law, basipetally from tips to root.
        r^n = sum of children r^n
        Tip radius = base_radius from config.
        The pipe-model exponent is read from pipe_exponent in config.
        """
        r0 = self.cfg.get('base_radius', 0.015)
        n = self.cfg.get('pipe_exponent', 2.0)

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
        max_radius = self.cfg.get('trunk_radius', r0)
        for branch in order:
            node_id = id(branch)
            kids = children[node_id]
            if not kids:
                # Tip node
                radii[node_id] = r0
            else:
                # Murray's law — capped at trunk_radius
                radii[node_id] = min(
                    sum(radii[id(k)]**n for k in kids) ** (1.0/n),
                    max_radius
                )

        # Preserve the pipe-model radii for selecting strongly supported
        # crown axes independently of later age and trunk-form additions.
        pipe_radii = radii.copy()

        age_cfg = self.cfg.get('age_thickening', {})
        if age_cfg.get('enabled', False):
            max_increment = age_cfg.get('max_radius_increment', 0.0)
            age_exponent = age_cfg.get(
                'age_exponent', age_cfg.get('exponent', 1.0)
            )
            support_exponent = age_cfg.get('support_exponent', 0.0)
            if max_increment < 0.0:
                raise ValueError(
                    "age_thickening max_radius_increment must be non-negative"
                )
            if age_exponent <= 0.0:
                raise ValueError(
                    "age_thickening age_exponent must be positive"
                )
            if support_exponent < 0.0:
                raise ValueError(
                    "age_thickening support_exponent must be non-negative"
                )

            oldest_step = min(branch.loop_index for branch in self.branches)
            newest_step = max(self.actual_loops, 0)
            total_age_span = max(1, newest_step - oldest_step)
            root_pipe_radius = radii[id(self.branches[0])]
            for branch in self.branches:
                age_fraction = (
                    (newest_step - branch.loop_index) / total_age_span
                )
                support_fraction = (
                    radii[id(branch)] / root_pipe_radius
                    if root_pipe_radius > 0.0 else 0.0
                )
                radii[id(branch)] += (
                    max_increment
                    * age_fraction ** age_exponent
                    * support_fraction ** support_exponent
                )

        support_cfg = self.cfg.get('supporting_branch_thickening', {})
        if support_cfg.get('enabled', False):
            max_increment = (
                support_cfg.get('max_radius_increment_multiplier', 0.0)
                * self.growth_dist
            )
            percentile = support_cfg.get('support_percentile', 90.0)
            exponent = support_cfg.get('exponent', 1.0)
            if max_increment < 0.0:
                raise ValueError(
                    "supporting_branch_thickening maximum increment must "
                    "be non-negative"
                )
            if not 0.0 <= percentile < 100.0:
                raise ValueError(
                    "supporting_branch_thickening support_percentile must "
                    "be in [0, 100)"
                )
            if exponent <= 0.0:
                raise ValueError(
                    "supporting_branch_thickening exponent must be positive"
                )

            prescribed_ids = getattr(self, '_prescribed_trunk_ids', set())
            crown = [
                branch for branch in self.branches
                if id(branch) not in prescribed_ids
            ]
            if crown and max_increment > 0.0:
                support_values = np.asarray(
                    [pipe_radii[id(branch)] for branch in crown],
                    dtype=float
                )
                threshold = float(np.percentile(support_values, percentile))
                strongest = float(np.max(support_values))
                span = strongest - threshold
                thickened = 0
                if span > 0.0:
                    for branch in crown:
                        support = pipe_radii[id(branch)]
                        if support <= threshold:
                            continue
                        weight = (support - threshold) / span
                        radii[id(branch)] += max_increment * weight ** exponent
                        thickened += 1
                print(
                    f"  Supporting-branch thickening: {thickened} crown "
                    f"nodes above percentile {percentile:.1f}, "
                    f"up to +{max_increment:.3f}"
                )

        transition_cfg = self.cfg.get('trunk_transition', {})
        if transition_cfg.get('enabled', False):
            transition_length = transition_cfg.get('length', 0.0)
            transition_exponent = transition_cfg.get('exponent', 1.0)
            if transition_length <= 0.0:
                raise ValueError(
                    "trunk_transition length must be greater than zero"
                )
            if transition_exponent <= 0.0:
                raise ValueError(
                    "trunk_transition exponent must be greater than zero"
                )

            # Follow the unbranched root axis to its first fork.  Blend the
            # final portion of that axis toward its best-supported child so
            # the leader flows into the crown without an oversized collar.
            trunk_axis = [self.branches[0]]
            fork = self.branches[0]
            while len(children[id(fork)]) == 1:
                fork = children[id(fork)][0]
                trunk_axis.append(fork)

            fork_children = children[id(fork)]
            if len(fork_children) > 1:
                target_radius = max(radii[id(kid)] for kid in fork_children)
                distance_to_fork = 0.0
                for index in range(len(trunk_axis) - 1, -1, -1):
                    branch = trunk_axis[index]
                    if distance_to_fork <= transition_length:
                        blend = (
                            1.0 - distance_to_fork / transition_length
                        ) ** transition_exponent
                        radii[id(branch)] = (
                            radii[id(branch)] * (1.0 - blend)
                            + target_radius * blend
                        )
                    if index > 0:
                        distance_to_fork += math.dist(
                            trunk_axis[index - 1].pos(), branch.pos()
                        )
                print(
                    f"  Trunk transition: {transition_length:.3f} to "
                    f"dominant-child radius {target_radius:.3f}"
                )

        trunk_form_cfg = self.cfg.get('trunk_form', {})
        if trunk_form_cfg.get('enabled', False):
            shaft_increment = trunk_form_cfg.get(
                'shaft_radius_increment', 0.0
            )
            shaft_exponent = trunk_form_cfg.get('shaft_radius_exponent', 1.0)
            flare_increment = trunk_form_cfg.get(
                'basal_flare_increment', 0.0
            )
            flare_length = trunk_form_cfg.get('basal_flare_length', 0.0)
            flare_exponent = trunk_form_cfg.get('basal_flare_exponent', 2.0)
            if shaft_increment < 0.0:
                raise ValueError(
                    "trunk_form shaft_radius_increment must be non-negative"
                )
            if shaft_exponent <= 0.0:
                raise ValueError(
                    "trunk_form shaft_radius_exponent must be positive"
                )
            if flare_increment < 0.0:
                raise ValueError(
                    "trunk_form basal_flare_increment must be non-negative"
                )
            if flare_increment > 0.0 and flare_length <= 0.0:
                raise ValueError(
                    "trunk_form basal_flare_length must be positive when "
                    "basal flare is used"
                )
            if flare_exponent <= 0.0:
                raise ValueError(
                    "trunk_form basal_flare_exponent must be positive"
                )

            if shaft_increment > 0.0 or flare_increment > 0.0:
                initial_trunk_length = getattr(
                    self, '_initial_trunk_length', 0.0
                )
                distance_from_root = 0.0
                node = self.branches[0]
                while True:
                    if (
                        shaft_increment > 0.0
                        and initial_trunk_length > 0.0
                    ):
                        shaft_fraction = max(
                            0.0,
                            1.0 - distance_from_root / initial_trunk_length
                        )
                        radii[id(node)] += (
                            shaft_increment
                            * shaft_fraction ** shaft_exponent
                        )
                    if distance_from_root <= flare_length:
                        flare_fraction = (
                            1.0 - distance_from_root / flare_length
                        )
                        radii[id(node)] += (
                            flare_increment
                            * flare_fraction ** flare_exponent
                        )
                    kids = children[id(node)]
                    if len(kids) != 1:
                        break
                    child = kids[0]
                    distance_from_root += math.dist(node.pos(), child.pos())
                    node = child
                if shaft_increment > 0.0:
                    print(
                        f"  Trunk shaft thickening: +{shaft_increment:.3f} "
                        f"at base, fading to crown"
                    )
            if flare_increment > 0.0:
                print(
                    f"  Basal flare: +{flare_increment:.3f} over "
                    f"{flare_length:.3f}"
                )

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

        return self._get_output_geometry()[0]

    def get_joints(self):
        """
        Returns list of (pos, radius) tuples for joint spheres.
        Radius matches the cylinder radius at each node.
        """
        if not hasattr(self, '_radii'):
            self._compute_murray_radii()

        return self._get_output_geometry()[1]

    def _get_output_geometry(self):
        """Build cylinder and joint geometry, optionally with curve subdivision."""
        if hasattr(self, '_output_geometry'):
            return self._output_geometry

        render_branches = self._get_render_branches()
        retained_ids = {id(branch) for branch in render_branches}
        positions = self._get_render_positions()
        base_radius = self.cfg.get('base_radius', 0.015)
        joint_mult = self.cfg.get('joint_radius_multiplier', 1.2)
        joint_cap = self.cfg.get('joint_radius_cap', base_radius * 10)
        subdivision_cfg = self.cfg.get('subdivision', {})

        render_children = {id(branch): [] for branch in render_branches}
        render_parents = {}
        for branch in render_branches[1:]:
            render_parent = self._get_render_parent(branch, retained_ids)
            if render_parent is not None:
                render_parents[id(branch)] = render_parent
                render_children[id(render_parent)].append(branch)

        if not subdivision_cfg.get('enabled', False):
            cylinders = []
            joints = []
            for branch in render_branches[1:]:
                render_parent = render_parents.get(id(branch))
                if render_parent is None:
                    continue
                radius = self._radii.get(id(branch), base_radius)
                cylinders.append((
                    positions[id(render_parent)], positions[id(branch)], radius
                ))
                joints.append((
                    positions[id(branch)], min(radius * joint_mult, joint_cap)
                ))
            self._output_geometry = (cylinders, joints)
            return self._output_geometry

        iterations = subdivision_cfg.get('iterations', 2)
        corner_cut_ratio = subdivision_cfg.get('corner_cut_ratio', 0.25)
        cylinders = []
        joint_by_position = {}

        # Optionally treat the best-supported child at each fork as the
        # continuation of its parent axis.  This lets corner cutting blend the
        # trunk through a fork instead of preserving a hard path endpoint
        # there; less-supported children remain independent lateral axes.
        continue_through_forks = subdivision_cfg.get(
            'continue_through_forks', False
        )
        primary_children = {}
        if continue_through_forks:
            for branch in render_branches:
                kids = render_children[id(branch)]
                if kids:
                    primary_children[id(branch)] = max(
                        kids,
                        key=lambda child: self._radii.get(
                            id(child), base_radius
                        )
                    )

            path_starts = []
            root = render_branches[0]
            if render_children[id(root)]:
                path_starts.append((root, primary_children[id(root)]))
            for base in render_branches:
                primary = primary_children.get(id(base))
                for child in render_children[id(base)]:
                    if child is not primary:
                        path_starts.append((base, child))
        else:
            path_starts = [
                (base, child)
                for base in render_branches
                if base.parent is None
                or len(render_children[id(base)]) != 1
                for child in render_children[id(base)]
            ]

        for base, first_node in path_starts:
                path = [base, first_node]
                node = first_node
                while render_children[id(node)]:
                    if continue_through_forks:
                        node = primary_children[id(node)]
                    elif len(render_children[id(node)]) == 1:
                        node = render_children[id(node)][0]
                    else:
                        break
                    path.append(node)

                samples = [
                    (
                        np.asarray(positions[id(branch)], dtype=float),
                        self._radii.get(id(branch), base_radius)
                    )
                    for branch in path
                ]
                refined = subdivide_polyline(
                    samples, iterations, corner_cut_ratio
                )

                for (p0, _), (p1, radius) in zip(refined, refined[1:]):
                    start = tuple(p0)
                    end = tuple(p1)
                    cylinders.append((start, end, radius))
                    joint_by_position[end] = min(radius * joint_mult, joint_cap)

        joints = list(joint_by_position.items())
        print(f"  Subdivided render skeleton: {len(render_branches) - 1} -> "
              f"{len(cylinders)} segments ({iterations} iterations, "
              f"corner cut={corner_cut_ratio:.3f}, "
              f"fork continuation={continue_through_forks})")
        self._output_geometry = (cylinders, joints)
        return self._output_geometry

    @staticmethod
    def _get_render_parent(branch, retained_ids):
        """Return the nearest retained ancestor of a render node."""
        render_parent = branch.parent
        while render_parent is not None and id(render_parent) not in retained_ids:
            render_parent = render_parent.parent
        return render_parent

    def _get_render_positions(self):
        """Return output positions, optionally relocated toward basal neighbors."""
        render_branches = self._get_render_branches()
        if not hasattr(self, '_render_positions'):
            positions = {id(branch): branch.pos() for branch in render_branches}
            relocation_cfg = self.cfg.get('branch_relocation', {})

            if relocation_cfg.get('enabled', False):
                fraction = relocation_cfg.get('basal_fraction', 0.5)
                if not 0.0 <= fraction <= 1.0:
                    raise ValueError("branch_relocation basal_fraction must be between 0 and 1")

                retained_ids = set(positions)
                original_positions = positions.copy()
                for branch in render_branches[1:]:
                    render_parent = self._get_render_parent(branch, retained_ids)
                    if render_parent is None:
                        continue
                    position = np.asarray(original_positions[id(branch)], dtype=float)
                    basal_position = np.asarray(
                        original_positions[id(render_parent)], dtype=float
                    )
                    positions[id(branch)] = tuple(
                        position + fraction * (basal_position - position)
                    )

                print(f"  Relocated {len(render_branches) - 1} render nodes "
                      f"{fraction:.3f} toward their basal neighbors")

            trunk_form_cfg = self.cfg.get('trunk_form', {})
            sway_amplitude = trunk_form_cfg.get('sway_amplitude', 0.0)
            initial_trunk_length = getattr(
                self, '_initial_trunk_length', 0.0
            )
            if (
                trunk_form_cfg.get('enabled', False)
                and sway_amplitude > 0.0
                and initial_trunk_length > 0.0
            ):
                rp = self.cfg.get('root_position', [0, 0, 0])
                sway_cycles = trunk_form_cfg.get('sway_cycles', 0.75)
                sway_phase = (
                    self.cfg['seed'] * 0.61803398875
                ) % (2.0 * math.pi)
                for branch in render_branches:
                    if id(branch) not in self._prescribed_trunk_ids:
                        continue
                    height_fraction = min(
                        1.0,
                        max(0.0, (branch.y - rp[1]) / initial_trunk_length)
                    )
                    envelope = math.sin(math.pi * height_fraction)
                    angle = (
                        2.0 * math.pi * sway_cycles * height_fraction
                        + sway_phase
                    )
                    position = np.asarray(positions[id(branch)], dtype=float)
                    position[0] += (
                        sway_amplitude * envelope * math.sin(angle)
                    )
                    position[2] += (
                        sway_amplitude * envelope
                        * math.sin(angle + 0.5 * math.pi)
                    )
                    positions[id(branch)] = tuple(position)

                print(
                    f"  Render-only trunk sway: amplitude "
                    f"{sway_amplitude:.3f}, cycles {sway_cycles:.3f}"
                )

            self._render_positions = positions

        return self._render_positions

    def _get_render_branches(self):
        """Return the original or decimated node list used for output geometry."""
        decimation_cfg = self.cfg.get('decimation', {})
        if not decimation_cfg.get('enabled', False):
            return self.branches

        if not hasattr(self, '_decimated_branches'):
            spacing_multiplier = decimation_cfg.get('spacing_multiplier', 2.0)
            minimum_spacing = spacing_multiplier * self.growth_dist
            self._decimated_branches = decimate_branches(
                self.branches, minimum_spacing
            )
            print(f"  Decimated render skeleton: {len(self.branches)} -> "
                  f"{len(self._decimated_branches)} nodes "
                  f"(minimum spacing={minimum_spacing:.3f})")

        return self._decimated_branches
    


    # =============================================================================
# 5. write_tree — outputs pbrt Include file
# =============================================================================

def write_tree(cfg, cylinders, joints, scene_files_root, index=0):
    """
    Writes scene_files/tree.pbrt — an Include file for scene.pbrt.
    Contains cylinders for branch segments and spheres for joints.
    All coordinates scaled from algorithm space to pbrt world space.
    """
    scale     = 1.0
    tx, ty, tz = 0.0, 0.0, 0.0

    trunk_r   = cfg['trunk_material']['reflectance']
    joint_r   = cfg['joint_material']['reflectance']

    out_path = os.path.join(scene_files_root, f'tree_{index}.pbrt')
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
        cx_ = -uy
        cy_ =  ux
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

    return out_path



# =============================================================================
# 6. run — entry point called from build_scene.py
# =============================================================================

def run(cfg, scene_files_root):
    """
    Entry point for space colonization tree generation.
    Called from build_scene.py when tree.enabled is true.

    Args:
        cfg          — full scene config dictionary
        scene_files_root — configured absolute scene-files directory

    Returns:
        relative path to tree.pbrt for use as Include directive,
        or None if tree is disabled.
    """
    from generate import configured_space_colonization_trees

    enabled = [
        tree
        for tree in configured_space_colonization_trees(cfg)
        if tree.get('enabled', False)
    ]
    if not enabled:
        return None
    if len(enabled) != 1:
        raise ValueError(
            'standalone space_col.py requires exactly one enabled tree; '
            'use generate.py for multiple trees'
        )
    tree_cfg = enabled[0]

    print(f"  Growing tree: {tree_cfg['num_leaves']} leaves, "
          f"{tree_cfg['max_loops']} max iterations...")

    # Build tree
    tree = Tree3D(tree_cfg)
    tree.grow()

    # Extract geometry
    cylinders = tree.get_cylinders()
    joints    = tree.get_joints()

    # Write pbrt Include file
    return write_tree(tree_cfg, cylinders, joints, scene_files_root)



# =============================================================================
# 7. main — command line entry point
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 space_col.py <config.json path>")
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

    result = run(cfg, scene_files_root)

    if result:
        print(f"  Tree Include file: {result}")
    else:
        print("  Tree disabled in config — nothing to do.")
    
