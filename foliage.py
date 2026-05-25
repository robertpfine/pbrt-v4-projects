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

class LeafBoundary:
    """
    Parametric leaf boundary in 2D local space.
    x axis — along leaf length (petiole to tip)
    y axis — across leaf width

    Supported types:
      ellipse  — simple elliptical boundary
      ovate    — wider near base, narrower at tip (most common dicot leaf)
    """

    def __init__(self, cfg):
        self.type   = cfg.get('type', 'ovate')
        self.length = cfg.get('length', 1.0)   # along x axis
        self.width  = cfg.get('width',  0.5)   # along y axis

    def contains(self, x, y):
        """Returns True if point (x,y) is inside the leaf boundary."""
        if self.type == 'ellipse':
            return self._ellipse(x, y)
        elif self.type == 'ovate':
            return self._ovate(x, y)
        return False

    def _ellipse(self, x, y):
        cx = self.length / 2
        return ((x - cx) / (self.length / 2))**2 + (y / (self.width / 2))**2 <= 1.0

    def _ovate(self, x, y):
        # Ovate: widest at ~1/3 from base, narrows toward tip
        # x in [0, length], y in [-width/2, width/2]
        if x < 0 or x > self.length:
            return False
        t = x / self.length  # normalized position 0=base 1=tip
        # Half-width varies along x: peaks at t=0.35, zero at t=0 and t=1
        half_w = self.width / 2 * 4 * t * (1 - t) * (1 + 0.4 * (0.35 - t))
        return abs(y) <= half_w

    def sample_poisson(self, n_sources, birth_dist, seed=42):
        """
        Dart throwing (Poisson disk) within boundary.
        Returns list of (x, y) auxin source positions.
        """
        random.seed(seed)
        sources  = []
        src_arr  = np.empty((0, 2))
        attempts = 0
        max_att  = n_sources * 50

        while len(sources) < n_sources and attempts < max_att:
            attempts += 1
            x = random.uniform(0, self.length)
            y = random.uniform(-self.width / 2, self.width / 2)

            if not self.contains(x, y):
                continue

            if len(sources) > 0:
                dists = np.sqrt(((src_arr[:, 0] - x)**2) +
                                ((src_arr[:, 1] - y)**2))
                if np.min(dists) < birth_dist:
                    continue

            sources.append((x, y))
            src_arr = (np.vstack([src_arr, [x, y]])
                       if len(sources) > 1 else np.array([[x, y]]))

        return sources
    

class LeafVenation:
    """
    2D space colonization for leaf venation.
    Runs in local leaf coordinate space.
    Reference: Runions et al. 2005, Section 3.

    Vein nodes grow toward auxin sources (attraction points).
    Sources removed when within kill distance dk.
    """

    def __init__(self, boundary, vcfg):
        self.boundary   = boundary
        self.D          = vcfg.get('D', 0.05)
        self.dk         = vcfg.get('dk_multiplier', 2.0) * self.D
        self.di         = vcfg.get('di_multiplier', 999.0) * self.D
        self.n_sources  = vcfg.get('num_sources', 200)
        self.birth_dist = vcfg.get('birth_dist', 0.05)
        self.max_loops  = vcfg.get('max_loops', 100)
        self.max_stuck  = vcfg.get('max_stuck', 5)

        # Generate auxin sources via Poisson disk
        self.sources = boundary.sample_poisson(
            self.n_sources, self.birth_dist
        )

        # Vein nodes — start from base of leaf (petiole attachment)
        # Single seed node at (0, 0) — base of leaf
        self.nodes  = [(0.0, 0.0)]
        self.edges  = []  # list of (parent_idx, child_idx)
        self.radii  = [0.0]  # will be computed via Murray's law

    def grow(self):
        """Run venation growth loop."""
        from scipy.spatial import KDTree

        sources    = list(self.sources)
        nodes      = self.nodes
        D          = self.D
        dk         = self.dk
        di         = self.di
        max_loops  = self.max_loops
        max_stuck  = self.max_stuck

        prev_count    = len(sources)
        stuck_iters   = 0
        initial_count = len(sources)

        for iteration in range(max_loops):
            if len(sources) < 3:
                break

            node_arr   = np.array(nodes)
            source_arr = np.array(sources)
            kdtree     = KDTree(node_arr)

            # For each source find closest node
            dists, indices = kdtree.query(source_arr)

            # Accumulate direction influences per node
            influence = {}
            to_remove = set()

            for i, (sx, sy) in enumerate(sources):
                dist  = dists[i]
                n_idx = indices[i]

                if dist < dk:
                    to_remove.add(i)
                    continue

                if dist <= di:
                    nx, ny = nodes[n_idx]
                    dx = sx - nx
                    dy = sy - ny
                    mag = math.sqrt(dx*dx + dy*dy)
                    if mag > 0:
                        dx /= mag
                        dy /= mag
                    if n_idx not in influence:
                        influence[n_idx] = [0.0, 0.0, 0]
                    influence[n_idx][0] += dx
                    influence[n_idx][1] += dy
                    influence[n_idx][2] += 1

            # Spawn new nodes
            for n_idx, (dx, dy, count) in influence.items():
                mag = math.sqrt(dx*dx + dy*dy)
                if mag > 0:
                    dx /= mag
                    dy /= mag
                nx, ny = nodes[n_idx]
                new_x = nx + dx * D
                new_y = ny + dy * D
                if self.boundary.contains(new_x, new_y):
                    new_idx = len(nodes)
                    nodes.append((new_x, new_y))
                    self.edges.append((n_idx, new_idx))
                    self.radii.append(0.0)

            # Remove reached sources
            sources = [s for i, s in enumerate(sources)
                       if i not in to_remove]

            # Stall detection
            if len(sources) == prev_count and len(sources) < initial_count:
                stuck_iters += 1
                if stuck_iters >= max_stuck:
                    break
            else:
                stuck_iters   = 0
                prev_count    = len(sources)

        self.nodes   = nodes
        self.sources = sources
        self._compute_radii()

    def _compute_radii(self):
        """Murray's law radius computation basipetally."""
        r0 = 0.003  # tip radius

        children = {i: [] for i in range(len(self.nodes))}
        for parent, child in self.edges:
            children[parent].append(child)

        # Post-order traversal
        order   = []
        visited = set()
        stack   = [0]
        while stack:
            n = stack[-1]
            kids = [k for k in children[n] if k not in visited]
            if kids:
                stack.append(kids[0])
            else:
                stack.pop()
                order.append(n)
                visited.add(n)

        radii = {}
        for n in order:
            kids = children[n]
            if not kids:
                radii[n] = r0
            else:
                radii[n] = min(
                    sum(radii[k]**2 for k in kids) ** 0.5,
                    0.015
                )
        self.radii = [radii.get(i, r0) for i in range(len(self.nodes))]
    





# =============================================================================
# 5. Leaf Mesh Generation
# =============================================================================

def generate_canonical_leaf(foliage_cfg):
    """
    Generate a single canonical leaf in local 2D space.
    Runs venation algorithm, builds mesh from vein network.
    Returns (nodes_2d, edges, radii, boundary) for later 3D placement.

    Local coordinate system:
      x — along leaf length (petiole=0 to tip=length)
      y — across leaf width
      z — out of leaf plane (for curvature)
    """
    leaf_cfg = foliage_cfg.get('leaf', {})
    vcfg     = leaf_cfg.get('venation', {})

    # Build boundary and run venation
    boundary = LeafBoundary(leaf_cfg)
    venation = LeafVenation(boundary, vcfg)
    venation.grow()

    print(f"  Canonical leaf: {len(venation.nodes)} vein nodes, "
          f"{len(venation.edges)} segments")

    return venation.nodes, venation.edges, venation.radii, boundary


def leaf_to_world(nodes_2d, pos, leaf_right, leaf_up, leaf_normal, leaf_cfg, scale):
    """
    Transform canonical leaf from local 2D space to world 3D space.
    Applies curvature deformation, then transport frame orientation.

    Local x -> leaf_right (across width)
    Local y -> leaf_up (along length, petiole to tip)
    Curvature -> leaf_normal displacement
    """
    midrib_k = leaf_cfg.get('midrib_curvature', 0.1)
    blade_k  = leaf_cfg.get('blade_curvature', 0.05)
    length   = leaf_cfg.get('length', 1.0)
    width    = leaf_cfg.get('width', 0.5)

    world_nodes = []
    for (lx, ly) in nodes_2d:
        t = ly / length if length > 0 else 0
        s = lx / (width / 2) if width > 0 else 0

        z_mid   = midrib_k * 4 * t * (1 - t)
        z_blade = blade_k * (1 - s*s)
        z       = z_mid + z_blade

        wx = (pos +
              lx * scale * leaf_right +
              ly * scale * leaf_up +
              z  * scale * leaf_normal)
        world_nodes.append(wx)

    return world_nodes


def make_disk_leaf(pos, leaf_right, leaf_up, leaf_normal, scale):
    """
    Fallback simple disk leaf — used if venation disabled.
    """
    n_segments = 8
    verts  = [pos]
    for i in range(n_segments):
        angle = 2 * math.pi * i / n_segments
        v = (pos +
             scale * math.cos(angle) * leaf_right +
             scale * math.sin(angle) * leaf_up)
        verts.append(v)
    indices = []
    for i in range(n_segments):
        indices.extend([0, i + 1, (i + 1) % n_segments + 1])
    return verts, indices

def triangulate_leaf_blade(boundary, resolution=20):
    """
    Option C — grid sampling within leaf boundary.
    Generates a triangulated mesh filling the leaf blade.
    
    Samples a regular grid within the bounding box,
    keeps points inside the boundary, Delaunay triangulates.
    
    Returns (points_2d, indices) where points_2d is list of (x,y)
    and indices is list of triangle vertex index triples.
    """
    from scipy.spatial import Delaunay

    length = boundary.length
    width  = boundary.width

    # Sample grid points inside boundary
    pts = []
    for i in range(resolution + 1):
        for j in range(resolution + 1):
            x = i * length / resolution
            y = -width/2 + j * width / resolution
            if boundary.contains(x, y):
                pts.append((x, y))

    # Add boundary perimeter points for clean edges
    n_perim = resolution * 2
    for k in range(n_perim):
        t = k / n_perim
        # Parametric boundary trace
        x = t * length
        if boundary.type == 'ovate':
            hw = boundary.width / 2 * 4 * t * (1 - t) * (1 + 0.4 * (0.35 - t))
        else:
            hw = boundary.width / 2 * math.sqrt(max(0, 1 - ((x - length/2)/(length/2))**2))
        if hw > 0:
            pts.append((x,  hw))
            pts.append((x, -hw))

    if len(pts) < 3:
        return [], []

    pts_arr = np.array(pts)
    tri     = Delaunay(pts_arr)

    # Filter triangles — keep only those whose centroid is inside boundary
    valid_indices = []
    for simplex in tri.simplices:
        cx = (pts_arr[simplex[0]][0] + pts_arr[simplex[1]][0] + pts_arr[simplex[2]][0]) / 3
        cy = (pts_arr[simplex[0]][1] + pts_arr[simplex[1]][1] + pts_arr[simplex[2]][1]) / 3
        if boundary.contains(cx, cy):
            valid_indices.extend(simplex.tolist())

    return pts, valid_indices


# =============================================================================
# 6. write_foliage
# =============================================================================

def write_foliage(placements, canonical_leaf, foliage_cfg, project_root):
    """
    Write scene_files/foliage.pbrt using pbrt-v4 instancing.
    Defines canonical leaf once as ObjectBegin/ObjectEnd,
    then places it with ObjectInstance + Transform for each placement.
    Reduces BVH from millions of primitives to one leaf definition.
    """
    scale    = foliage_cfg.get('leaf_scale', 0.3)
    color    = foliage_cfg.get('vein_color', [0.15, 0.35, 0.10])
    leaf_cfg = foliage_cfg.get('leaf', {})
    out_path = os.path.join(project_root, 'scene_files', 'foliage.pbrt')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    lines = ['# foliage.pbrt — generated by foliage.py', '']

    if canonical_leaf is not None:
        nodes_2d, edges, radii, boundary = canonical_leaf
        blade_cfg      = leaf_cfg.get('blade', {})
        show_veins_only = leaf_cfg.get('show_veins_only', False)

        # Build active color palette
        palette = blade_cfg.get('palette', [])
        active_colors = [e['color'] for e in palette if e.get('enabled', True)]
        if not active_colors:
            active_colors = [blade_cfg.get('color', [0.08, 0.25, 0.06])]

        # --- Define canonical leaf variants — one per palette color ---
        # Pre-compute geometry shared across all variants — done once
        blade_pts, blade_idx = [], []
        if blade_cfg.get('enabled', False) and not show_veins_only:
            blade_pts, blade_idx = triangulate_leaf_blade(
                boundary,
                resolution=blade_cfg.get('resolution', 20)
            )

        identity_pos    = np.array([0.0, 0.0, 0.0])
        identity_right  = np.array([1.0, 0.0, 0.0])
        identity_up     = np.array([0.0, 1.0, 0.0])
        identity_normal = np.array([0.0, 0.0, 1.0])

        world_blade = []
        if blade_pts:
            world_blade = leaf_to_world(
                blade_pts, identity_pos,
                identity_right, identity_up, identity_normal,
                leaf_cfg, scale
            )

        local_nodes = leaf_to_world(
            nodes_2d, identity_pos,
            identity_right, identity_up, identity_normal,
            leaf_cfg, scale
        )
        min_vein = leaf_cfg.get('min_vein_width', 0.005)

        # Pre-compute vein ribbon geometry — done once
        vein_quads = []
        for parent_idx, child_idx in edges:
            p0 = local_nodes[parent_idx]
            p1 = local_nodes[child_idx]
            r  = max(radii[parent_idx] * scale, min_vein)
            perp = np.cross(p1 - p0, identity_normal)
            pmag = np.linalg.norm(perp)
            if pmag < 1e-6:
                continue
            perp /= pmag
            v0 = p0 + perp * r
            v1 = p0 - perp * r
            v2 = p1 - perp * r
            v3 = p1 + perp * r
            vein_quads.append((v0, v1, v2, v3))

        # Loop over palette colors — emit one ObjectBegin block per color
        for color_idx, blade_color in enumerate(active_colors):
            lines += [f'ObjectBegin "leaf_{color_idx}"', '']

            # Blade surface — color varies per variant
            if world_blade and blade_idx:
                pts_str = '  '.join(
                    f'{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}'
                    for v in world_blade
                )
                idx_str = ' '.join(str(i) for i in blade_idx)
                lines += [
                    'AttributeBegin',
                    f'    Material "diffuse"  "rgb reflectance" '
                    f'[ {blade_color[0]} {blade_color[1]} {blade_color[2]} ]',
                    '    Shape "trianglemesh"',
                    f'        "integer indices" [ {idx_str} ]',
                    f'        "point3 P"        [ {pts_str} ]',
                    'AttributeEnd',
                    ''
                ]

            # Vein ribbons — same vein_color across all variants
            for v0, v1, v2, v3 in vein_quads:
                pts = ' '.join(
                    f'{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}'
                    for v in [v0, v1, v2, v3]
                )
                lines += [
                    'AttributeBegin',
                    f'    Material "diffuse"  "rgb reflectance" '
                    f'[ {color[0]} {color[1]} {color[2]} ]',
                    '    Shape "trianglemesh"',
                    '        "integer indices" [ 0 1 2  0 2 3 ]',
                    f'        "point3 P"        [ {pts} ]',
                    'AttributeEnd',
                    ''
                ]

            lines += ['ObjectEnd', '']

        # --- Place instances ---
        n_variants = len(active_colors)
        for pos, leaf_right, leaf_up, leaf_normal in placements:
            variant = random.randint(0, n_variants - 1)
            # Build 4x4 transform matrix from transport frame
            # Columns: [leaf_right | leaf_up | leaf_normal | pos]
            m = np.eye(4)
            m[0:3, 0] = leaf_right
            m[0:3, 1] = leaf_up
            m[0:3, 2] = leaf_normal
            m[0:3, 3] = pos

            # pbrt Transform takes row-major 4x4
            mt = m.T.flatten()
            mt_str = ' '.join(f'{v:.6f}' for v in mt)

            lines += [
                'AttributeBegin',
                f'    Transform [ {mt_str} ]',
                f'    ObjectInstance "leaf_{variant}"',
                'AttributeEnd',
                ''
            ]

    else:
        # Fallback — disk placeholders without instancing
        for pos, leaf_right, leaf_up, leaf_normal in placements:
            verts, indices = make_disk_leaf(
                pos, leaf_right, leaf_up, leaf_normal, scale
            )
            pts_str = '  '.join(
                f'{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}' for v in verts
            )
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
    Phase 3: Generate canonical leaf via venation algorithm
    Phase 5: Transform leaf to each placement
    Phase 6: Write foliage.pbrt
    """
    print("  Computing parallel transport frames...")
    frames = compute_transport_frames(tree)

    print("  Computing phyllotaxis placement...")
    placements = compute_phyllotaxis_points(tree, frames, foliage_cfg)
    print(f"  Leaf placements: {len(placements)}")

    print("  Generating canonical leaf via venation...")
    canonical_leaf = generate_canonical_leaf(foliage_cfg)

    print("  Writing foliage geometry...")
    write_foliage(placements, canonical_leaf, foliage_cfg, project_root)