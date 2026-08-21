"""Deterministic parametric L-system structures for PBRT plant models."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Segment:
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    radius0: float
    radius1: float
    kind: str


def christmas_tree(config):
    """Expand a simple 3D conifer grammar into tapered woody segments.

    The axial production repeats a trunk internode followed by a whorl.  Each
    whorl expands into radial primary branches; the branch production adds
    alternating lateral branchlets.  Length and radius are parameters carried
    by the symbols, producing the characteristic conical envelope.
    """

    height = float(config.get("height", 80.0))
    levels = int(config.get("levels", 18))
    crown_base = float(config.get("crown_base", 8.0))
    whorl_size = int(config.get("whorl_size", 7))
    max_branch = float(config.get("max_branch_length", 24.0))
    min_branch = float(config.get("min_branch_length", 2.5))
    base_radius = float(config.get("base_radius", 2.2))
    tip_radius = float(config.get("tip_radius", 0.35))
    branch_radius = float(config.get("branch_radius", 0.65))
    branchlets = int(config.get("branchlets_per_side", 5))
    branchlet_ratio = float(config.get("branchlet_length_ratio", 0.34))
    droop = float(config.get("droop", 0.12))
    seed = int(config.get("seed", 1))
    if levels < 2 or whorl_size < 2 or height <= 0:
        raise ValueError("invalid Christmas-tree L-system parameters")

    segments = []
    dy = height / levels
    # Production A(h,r) -> F(h,r) W(h) A(h+1,r')
    for level in range(levels):
        y0, y1 = level * dy, (level + 1) * dy
        f0, f1 = level / levels, (level + 1) / levels
        r0 = base_radius * (1.0 - f0) ** 0.72 + tip_radius * f0
        r1 = base_radius * (1.0 - f1) ** 0.72 + tip_radius * f1
        segments.append(Segment((0, y0, 0), (0, y1, 0), r0, r1, "wood"))
        if y1 < crown_base:
            continue

        crown_t = (y1 - crown_base) / max(1e-6, height - crown_base)
        primary_length = max_branch * (1.0 - crown_t) ** 0.72 + min_branch * crown_t
        phase = level * 137.5 + seed * 17.0
        for arm in range(whorl_size):
            azimuth = math.radians(phase + arm * 360.0 / whorl_size)
            ux, uz = math.cos(azimuth), math.sin(azimuth)
            px, pz = -uz, ux
            start = (0.0, y1, 0.0)
            previous = start
            # Production B(l) -> F(l/3) F(l/3) F(l/3), gently drooping.
            primary_points = []
            for step in range(1, 4):
                t = step / 3.0
                distance = primary_length * t
                y = y1 + primary_length * (0.10 * t - droop * t * t)
                current = (ux * distance, y, uz * distance)
                pr0 = branch_radius * (1.0 - 0.72 * (step - 1) / 3.0)
                pr1 = branch_radius * (1.0 - 0.72 * step / 3.0)
                segments.append(Segment(previous, current, pr0, pr1, "wood"))
                previous = current
                primary_points.append(current)

            # Production T(l) -> [+(a)F(s)][-(a)F(s)] along each primary.
            for twig_index in range(1, branchlets + 1):
                t = twig_index / (branchlets + 1)
                distance = primary_length * t
                base = (
                    ux * distance,
                    y1 + primary_length * (0.10 * t - droop * t * t),
                    uz * distance,
                )
                remaining = primary_length * (1.0 - t)
                twig_length = max(0.8, remaining * branchlet_ratio)
                for side in (-1.0, 1.0):
                    forward = 0.28
                    end = (
                        base[0] + twig_length * (side * px + forward * ux),
                        base[1] + twig_length * (0.16 - 0.08 * t),
                        base[2] + twig_length * (side * pz + forward * uz),
                    )
                    segments.append(Segment(
                        base, end,
                        max(0.10, branch_radius * 0.34),
                        max(0.045, branch_radius * 0.10),
                        "foliage",
                    ))
    return segments


def _normalize(v):
    length = math.sqrt(sum(component * component for component in v))
    return tuple(component / max(1e-9, length) for component in v)


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _noise(value, seed):
    raw = math.sin(value * 12.9898 + seed * 78.233) * 43758.5453
    return 2.0 * (raw - math.floor(raw)) - 1.0


def live_oak(config):
    """Expand a sympodial L-system into a mature live-oak skeleton.

    The trunk terminates early and promotes several lateral modules to nearly
    equal vigor. Descendant axes bifurcate asymmetrically, sag while heavy, and
    turn upward near their tips. Parameters carried by each axis include order,
    vigor, length, radius, direction, and a deterministic variation key.
    """

    trunk_height = float(config.get("trunk_height", 18.0))
    trunk_segments = int(config.get("trunk_segments", 6))
    trunk_base_radius = float(config.get("base_radius", 4.2))
    scaffold_count = int(config.get("scaffold_count", 6))
    scaffold_length = float(config.get("scaffold_length", 43.0))
    scaffold_radius = float(config.get("scaffold_radius", 2.25))
    recursion_depth = int(config.get("recursion_depth", 4))
    path_segments = int(config.get("path_segments", 5))
    base_sag = float(config.get("base_sag", 0.055))
    radius_sag = float(config.get("radius_sag", 0.018))
    tip_lift = float(config.get("tip_lift", 0.34))
    lateral_curve = float(config.get("lateral_curve", 0.10))
    bolt_turn = float(config.get("bolt_turn", 0.28))
    primary_sag = float(config.get("primary_sag", 0.075))
    primary_lift = float(config.get("primary_lift", 0.035))
    primary_wave_vertical = float(config.get("primary_wave_vertical", 0.0))
    primary_wave_lateral = float(config.get("primary_wave_lateral", 0.0))
    primary_wave_cycles = float(config.get("primary_wave_cycles", 1.0))
    ground_clearance = float(config.get("ground_clearance", 0.6))
    attachment_start = float(config.get("attachment_start", 0.24))
    attachment_end = float(config.get("attachment_end", 0.70))
    scaffold_elevation = float(config.get("scaffold_elevation", 0.08))
    scaffold_elevation_range = float(config.get("scaffold_elevation_range", 0.18))
    scaffold_vigor = tuple(float(v) for v in config.get(
        "scaffold_vigor", [1.0] * scaffold_count
    ))
    scaffold_sag = tuple(float(v) for v in config.get(
        "scaffold_sag", [1.0] * scaffold_count
    ))
    seed = int(config.get("seed", 11))
    segments = []

    trunk_points = [(0.0, 0.0, 0.0)]
    for index in range(1, trunk_segments + 1):
        t = index / trunk_segments
        trunk_points.append((
            0.65 * math.sin(t * 2.2),
            trunk_height * t,
            0.45 * math.sin(t * 3.1 + 0.7),
        ))
    for index in range(trunk_segments):
        t0, t1 = index / trunk_segments, (index + 1) / trunk_segments
        segments.append(Segment(
            trunk_points[index], trunk_points[index + 1],
            trunk_base_radius * (1.0 - 0.58 * t0),
            trunk_base_radius * (1.0 - 0.58 * t1),
            "wood",
        ))

    balanced = config.get("balanced_scaffolds")
    if balanced and balanced.get("enabled", False):
        # Environmentally sensitive parametric L-system experiment. Each
        # active Bud proposes F modules; the global derivation selects the
        # production that minimizes the crown's horizontal center of mass.
        step_length = float(balanced.get("segment_length", 5.0))
        momentum = float(balanced.get("momentum", 0.82))
        outward_bias = float(balanced.get("outward_bias", 0.16))
        phototropism = float(balanced.get("phototropism", 0.14))
        proprioception = float(balanced.get("proprioception", 0.20))
        target_vertical = float(balanced.get("target_vertical", 0.34))
        light_direction = _normalize(tuple(
            float(value) for value in balanced.get(
                "light_direction", [0.0, 1.0, 0.0]
            )
        ))
        turn_strength = float(balanced.get("turn_strength", 0.14))
        turn_cost = float(balanced.get("turn_cost", 0.035))
        urgency = float(balanced.get("completion_urgency", 0.08))
        bud_specs = balanced.get("buds", [])
        if len(bud_specs) < 2:
            raise ValueError("balanced_scaffolds requires at least two buds")

        states = []
        for bud_index, spec in enumerate(bud_specs):
            attachment_fraction = float(spec.get("attachment_fraction", 0.55))
            attachment_index = min(
                trunk_segments,
                max(1, round(trunk_segments * attachment_fraction)),
            )
            azimuth = math.radians(float(spec.get("azimuth", bud_index * 137.5)))
            elevation = float(spec.get("elevation", 0.12))
            direction = _normalize((
                math.cos(azimuth), elevation, math.sin(azimuth),
            ))
            states.append({
                "name": str(spec.get("name", f"bud_{bud_index}")),
                "position": trunk_points[attachment_index],
                "direction": direction,
                "outward": direction,
                "base_radius": float(spec.get("radius", scaffold_radius)),
                "tip_ratio": float(spec.get("tip_ratio", 0.40)),
                "steps": max(1, int(spec.get("steps", 12))),
                "wave_amplitude": float(spec.get("wave_amplitude", 0.0)),
                "wave_cycles": float(spec.get("wave_cycles", 1.0)),
                "wave_phase": math.radians(float(spec.get("wave_phase", 0.0))),
                "mass": 0.0,
                "grown": 0,
            })

        load_x = 0.0
        load_z = 0.0
        total_mass = 0.0
        coupled_pair = balanced.get("coupled_pair", {})
        if coupled_pair.get("enabled", False):
            if len(states) != 2:
                raise ValueError("coupled_pair mode requires exactly two buds")
            coupling = float(coupled_pair.get("direction_coupling", 0.85))
            pair_periods = min(
                int(coupled_pair.get("growth_periods", 16)),
                states[0]["steps"], states[1]["steps"],
            )

            def grow_pair_segment(state, direction):
                """Append one F module and return its gravitational mass."""

                progress0 = state["grown"] / state["steps"]
                progress1 = (state["grown"] + 1) / state["steps"]
                end = tuple(
                    state["position"][axis] + direction[axis] * step_length
                    for axis in range(3)
                )
                tip_radius = state["base_radius"] * state["tip_ratio"]
                r0 = state["base_radius"] + (
                    tip_radius - state["base_radius"]
                ) * progress0 ** 1.35
                r1 = state["base_radius"] + (
                    tip_radius - state["base_radius"]
                ) * progress1 ** 1.35
                mass = 0.5 * (r0 * r0 + r1 * r1) * step_length
                midpoint = tuple(
                    0.5 * (state["position"][axis] + end[axis])
                    for axis in range(3)
                )
                segments.append(Segment(
                    state["position"], end, r0, r1, "wood",
                ))
                state["position"] = end
                state["direction"] = direction
                state["grown"] += 1
                state["mass"] += mass
                return mass, midpoint

            for period in range(pair_periods):
                driver, responder = states
                driver_previous = driver["direction"]
                driver_progress = driver["grown"] / driver["steps"]
                driver_side = _normalize(_cross(
                    (0.0, 1.0, 0.0), driver_previous
                ))
                driver_wave = driver["wave_amplitude"] * math.sin(
                    2.0 * math.pi * driver["wave_cycles"] * driver_progress
                    + driver["wave_phase"]
                )
                driver_vertical_deficit = max(
                    0.0, target_vertical - driver_previous[1]
                )
                driver_direction = _normalize((
                    momentum * driver_previous[0]
                    + outward_bias * driver["outward"][0]
                    + phototropism * light_direction[0]
                    + driver_wave * driver_side[0],
                    momentum * driver_previous[1]
                    + outward_bias * driver["outward"][1]
                    + phototropism * light_direction[1]
                    + proprioception * driver_vertical_deficit,
                    momentum * driver_previous[2]
                    + outward_bias * driver["outward"][2]
                    + phototropism * light_direction[2]
                    + driver_wave * driver_side[2],
                ))
                driver_mass, driver_midpoint = grow_pair_segment(
                    driver, driver_direction
                )
                load_x += driver_mass * driver_midpoint[0]
                load_z += driver_mass * driver_midpoint[2]
                total_mass += driver_mass

                # The responder receives the opposite horizontal change in
                # the driver's direction vector. Segment mass scales the
                # response, so equal masses produce approximately equal and
                # opposite directional changes.
                direction_change = (
                    driver_direction[0] - driver_previous[0],
                    0.0,
                    driver_direction[2] - driver_previous[2],
                )
                responder_previous = responder["direction"]
                responder_progress = responder["grown"] / responder["steps"]
                responder_tip = (
                    responder["base_radius"] * responder["tip_ratio"]
                )
                responder_r0 = responder["base_radius"] + (
                    responder_tip - responder["base_radius"]
                ) * responder_progress ** 1.35
                responder_mass_estimate = responder_r0 * responder_r0 * step_length
                mass_ratio = driver_mass / max(1e-8, responder_mass_estimate)
                responder_vertical_deficit = max(
                    0.0, target_vertical - responder_previous[1]
                )
                responder_direction = _normalize((
                    momentum * responder_previous[0]
                    + outward_bias * responder["outward"][0]
                    + phototropism * light_direction[0]
                    - coupling * mass_ratio * direction_change[0],
                    momentum * responder_previous[1]
                    + outward_bias * responder["outward"][1]
                    + phototropism * light_direction[1]
                    + proprioception * responder_vertical_deficit,
                    momentum * responder_previous[2]
                    + outward_bias * responder["outward"][2]
                    + phototropism * light_direction[2]
                    - coupling * mass_ratio * direction_change[2],
                ))
                responder_mass, responder_midpoint = grow_pair_segment(
                    responder, responder_direction
                )
                load_x += responder_mass * responder_midpoint[0]
                load_z += responder_mass * responder_midpoint[2]
                total_mass += responder_mass

            if balanced.get("report_balance", False):
                center_x = load_x / total_mass if total_mass else 0.0
                center_z = load_z / total_mass if total_mass else 0.0
                print("Coupled two-branch growth:")
                for state in states:
                    print(
                        f"  {state['name']}: {state['grown']} periods, "
                        f"mass {state['mass']:.1f}, direction "
                        f"({state['direction'][0]:.3f}, "
                        f"{state['direction'][1]:.3f}, "
                        f"{state['direction'][2]:.3f})"
                    )
                print(
                    f"  crown horizontal COM: ({center_x:.3f}, {center_z:.3f}), "
                    f"offset {math.hypot(center_x, center_z):.3f}"
                )
            return segments

        capacity = sum(state["steps"] for state in states)
        remaining_segments = min(
            capacity, max(1, int(balanced.get("growth_budget", capacity)))
        )
        while remaining_segments:
            best = None
            for state_index, state in enumerate(states):
                if state["grown"] >= state["steps"]:
                    continue
                progress0 = state["grown"] / state["steps"]
                progress1 = (state["grown"] + 1) / state["steps"]
                side = _normalize(_cross(
                    (0.0, 1.0, 0.0), state["direction"]
                ))
                # Balance selects the bud, but does not steer it. Local axis
                # direction is governed by momentum, light seeking, outward
                # expansion, and correction of excessive droop.
                vertical_deficit = max(
                    0.0, target_vertical - state["direction"][1]
                )
                wave_angle = (
                    2.0 * math.pi * state["wave_cycles"] * progress0
                    + state["wave_phase"]
                )
                wave_steering = (
                    state["wave_amplitude"] * math.sin(wave_angle)
                )
                for turn in (0.0,):
                    direction = _normalize((
                        momentum * state["direction"][0]
                        + outward_bias * state["outward"][0]
                        + phototropism * light_direction[0]
                        + wave_steering * side[0]
                        + turn_strength * turn * side[0],
                        momentum * state["direction"][1]
                        + outward_bias * state["outward"][1]
                        + phototropism * light_direction[1]
                        + proprioception * vertical_deficit,
                        momentum * state["direction"][2]
                        + outward_bias * state["outward"][2]
                        + phototropism * light_direction[2]
                        + wave_steering * side[2]
                        + turn_strength * turn * side[2],
                    ))
                    end = tuple(
                        state["position"][axis] + direction[axis] * step_length
                        for axis in range(3)
                    )
                    tip_radius = state["base_radius"] * state["tip_ratio"]
                    r0 = state["base_radius"] + (
                        tip_radius - state["base_radius"]
                    ) * progress0 ** 1.35
                    r1 = state["base_radius"] + (
                        tip_radius - state["base_radius"]
                    ) * progress1 ** 1.35
                    mass = 0.5 * (r0 * r0 + r1 * r1) * step_length
                    midpoint_x = 0.5 * (state["position"][0] + end[0])
                    midpoint_z = 0.5 * (state["position"][2] + end[2])
                    next_mass = total_mass + mass
                    next_load_x = load_x + mass * midpoint_x
                    next_load_z = load_z + mass * midpoint_z
                    center_offset = math.hypot(
                        next_load_x / next_mass,
                        next_load_z / next_mass,
                    )
                    unfinished = 1.0 - progress0
                    score = (
                        center_offset
                        + turn_cost * abs(turn)
                        - urgency * unfinished
                    )
                    candidate = (
                        score, state_index, turn, direction, end,
                        r0, r1, mass, next_load_x, next_load_z,
                    )
                    if best is None or candidate[:3] < best[:3]:
                        best = candidate

            (_, state_index, _, direction, end, r0, r1, mass,
             load_x, load_z) = best
            state = states[state_index]
            segments.append(Segment(
                state["position"], end, r0, r1, "wood",
            ))
            state["position"] = end
            state["direction"] = direction
            state["grown"] += 1
            state["mass"] += mass
            total_mass += mass
            remaining_segments -= 1
        if balanced.get("report_balance", False):
            center_x = load_x / total_mass if total_mass else 0.0
            center_z = load_z / total_mass if total_mass else 0.0
            print("Balanced-scaffold allocation:")
            for state in states:
                print(
                    f"  {state['name']}: {state['grown']} segments, "
                    f"mass {state['mass']:.1f}"
                )
            print(
                f"  crown horizontal COM: ({center_x:.3f}, {center_z:.3f}), "
                f"offset {math.hypot(center_x, center_z):.3f}"
            )
        return segments

    def grow_axis(start, direction, length, radius, depth, key, sag_scale=1.0):
        """Production O(d,v) -> curved F sequence plus asymmetric O children."""
        order = recursion_depth - depth
        direction = _normalize(direction)
        horizontal = _normalize((direction[0], 0.0, direction[2]))
        side = _normalize(_cross((0.0, 1.0, 0.0), horizontal))
        previous = start
        points = []
        local_direction = direction
        axis_direction = direction
        wave_phase = math.pi * _noise(key + 8.3, seed)
        for step in range(1, path_segments + 1):
            t = step / path_segments
            variation = _noise(key + step * 0.37, seed)
            # Lightning-like axes hold direction, then make sparse decisive
            # turns. Major limbs sag and persist laterally; distal orders lift.
            turn = 0.0
            if step in (max(2, path_segments // 3), max(3, 2 * path_segments // 3)):
                turn = bolt_turn * variation / (1.0 + 0.20 * order)
            order_fraction = order / max(1, recursion_depth)
            sag = (
                primary_sag * sag_scale * (1.0 - order_fraction)
                + (base_sag + radius_sag * radius) * 0.30
            ) * (1.0 - t)
            lift = (
                primary_lift * (1.0 - order_fraction)
                + tip_lift * order_fraction
            ) * t * t
            step_length = length / path_segments
            if order == 0 and (primary_wave_vertical or primary_wave_lateral):
                # Major live-oak scaffolds undulate around a persistent lateral
                # axis. Constructing their points from that axis prevents the
                # wave from accumulating into a permanent upward/downward turn.
                angle = 2.0 * math.pi * primary_wave_cycles * t + wave_phase
                lateral_offset = primary_wave_lateral * length * math.sin(angle)
                vertical_offset = primary_wave_vertical * length * math.sin(
                    angle + 0.5 * math.pi
                )
                current = tuple(
                    start[i] + axis_direction[i] * length * t
                    + side[i] * lateral_offset
                    + (vertical_offset if i == 1 else 0.0)
                    for i in range(3)
                )
                local_direction = _normalize(tuple(
                    current[i] - previous[i] for i in range(3)
                ))
            else:
                local_direction = _normalize((
                    local_direction[0] + side[0] * turn,
                    local_direction[1] - sag + lift,
                    local_direction[2] + side[2] * turn,
                ))
                current = tuple(
                    previous[i] + local_direction[i] * step_length
                    for i in range(3)
                )
            if current[1] < ground_clearance:
                current = (current[0], ground_clearance, current[2])
                local_direction = _normalize((
                    local_direction[0], abs(local_direction[1]) + 0.32,
                    local_direction[2],
                ))
            axis_taper = 0.34 + 0.28 * order_fraction
            r0 = radius * (1.0 - axis_taper * (step - 1) / path_segments)
            r1 = radius * (1.0 - axis_taper * step / path_segments)
            segments.append(Segment(previous, current, r0, r1, "wood"))
            previous = current
            points.append((current, local_direction, side))

        if depth <= 0 or length < 2.0:
            return

        # Two unequal laterals plus a weakened continuation create sympodial
        # hierarchy without the repeated regular whorls of the conifer.
        attachment_indices = (max(1, path_segments // 2), path_segments - 1)
        for child_index, attachment_index in enumerate(attachment_indices):
            base, tangent, local_side = points[attachment_index]
            sign = -1.0 if (int(key * 10) + child_index) % 2 else 1.0
            spread = 0.62 + 0.18 * _noise(key + child_index * 1.7, seed)
            upward = 0.24 + 0.18 * (recursion_depth - depth) / max(1, recursion_depth)
            child_direction = _normalize((
                tangent[0] * 0.42 + sign * local_side[0] * spread,
                tangent[1] * 0.28 + upward,
                tangent[2] * 0.42 + sign * local_side[2] * spread,
            ))
            ratio = 0.53 + 0.10 * _noise(key + child_index * 2.3, seed)
            grow_axis(
                base, child_direction, length * ratio, radius * 0.57,
                depth - 1, key * 1.91 + child_index + 1.0,
                max(0.22, sag_scale * 0.58),
            )

        continuation_lift = 0.035 + 0.20 * order_fraction
        continuation = _normalize((
            local_direction[0],
            local_direction[1] + continuation_lift,
            local_direction[2],
        ))
        grow_axis(
            previous, continuation, length * 0.44, radius * 0.50,
            depth - 1, key * 2.17 + 4.0,
            max(0.22, sag_scale * 0.52),
        )

    for scaffold in range(scaffold_count):
        fraction = scaffold / max(1, scaffold_count - 1)
        vigor = scaffold_vigor[scaffold % len(scaffold_vigor)]
        trunk_index = min(
            trunk_segments,
            max(2, int(trunk_segments * (
                attachment_start + (attachment_end - attachment_start) * fraction
            ))),
        )
        start = trunk_points[trunk_index]
        azimuth = math.radians(
            scaffold * 137.5 + seed * 9.0 + 31.0 * _noise(scaffold + 0.8, seed)
        )
        elevation = (
            scaffold_elevation
            + scaffold_elevation_range * fraction
            + 0.055 * _noise(scaffold, seed)
        )
        direction = (math.cos(azimuth), elevation, math.sin(azimuth))
        length = scaffold_length * vigor * (1.0 - 0.15 * fraction) * (
            1.0 + 0.12 * _noise(scaffold + 0.4, seed)
        )
        grow_axis(
            start, direction, length,
            scaffold_radius * math.sqrt(vigor) * (1.0 - 0.16 * fraction),
            recursion_depth, scaffold + 1.0,
            scaffold_sag[scaffold % len(scaffold_sag)],
        )
    return segments
