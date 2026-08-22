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
                "bend_period": int(spec.get("bend_period", -1)),
                "bend_angle": math.radians(float(spec.get("bend_angle", 0.0))),
                "bend_events": {
                    int(event["period"]): {
                        "yaw": math.radians(float(
                            event.get("yaw", event.get("angle", 0.0))
                        )),
                        "pitch": math.radians(float(event.get("pitch", 0.0))),
                        "hold": max(0, int(event.get("hold", 0))),
                    }
                    for event in spec.get("bend_events", [])
                },
                "held_direction": None,
                "hold_remaining": 0,
                "response_share_total": 0.0,
                "mass": 0.0,
                "grown": 0,
                "trajectory": [],
                "horizontal_periods": max(-1, int(spec.get(
                    "horizontal_establishment_periods", -1
                ))),
                "rise_transition_periods": max(1, int(spec.get(
                    "rise_transition_periods", 8
                ))),
                "lateral_attachment_period": max(1, int(spec.get(
                    "lateral_attachment_period", 10
                ))),
            })

        load_x = 0.0
        load_z = 0.0
        total_mass = 0.0
        coupled_group = balanced.get("coupled_group", {})
        if coupled_group.get("enabled", False):
            coupling = float(coupled_group.get("direction_coupling", 0.85))
            response_delay = max(0, int(coupled_group.get("response_delay", 0)))
            horizontal_periods = max(0, int(
                coupled_group.get("horizontal_establishment_periods", 0)
            ))
            horizontal_max_vertical = max(0.0, float(
                coupled_group.get("horizontal_max_vertical", 0.08)
            ))

            def apply_rise_schedule(direction, state, period):
                """Hold an axis lateral, then release it upward gradually."""

                establishment = state["horizontal_periods"]
                if establishment < 0:
                    establishment = horizontal_periods
                transition = state["rise_transition_periods"]
                if period < establishment:
                    maximum_vertical = horizontal_max_vertical
                elif period < establishment + transition:
                    progress = (period - establishment + 1) / transition
                    maximum_vertical = (
                        horizontal_max_vertical
                        + progress * (target_vertical - horizontal_max_vertical)
                    )
                else:
                    return direction
                return _normalize((
                    direction[0],
                    min(direction[1], maximum_vertical),
                    direction[2],
                ))
            group_periods = min(
                int(coupled_group.get("growth_periods", 16)),
                *(state["steps"] for state in states),
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
                state["trajectory"].append({
                    "position": end,
                    "direction": direction,
                    "radius": r1,
                })
                return mass, midpoint

            driver_change_history = []
            for period in range(group_periods):
                driver = states[0]
                responders = states[1:]
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
                driver_direction = apply_rise_schedule(
                    driver_direction, driver, period
                )
                if driver["hold_remaining"] > 0:
                    driver_direction = driver["held_direction"]
                    driver["hold_remaining"] -= 1
                bend_event = driver["bend_events"].get(driver["grown"])
                if bend_event is None and driver["grown"] == driver["bend_period"]:
                    bend_event = {
                        "yaw": driver["bend_angle"], "pitch": 0.0, "hold": 0,
                    }
                if bend_event is not None:
                    # A discrete parametric-L-system turn command. Rotate the
                    # driver's horizontal heading while retaining its current
                    # vertical component; the responder is not told about the
                    # bend except through the measured direction-vector change.
                    cosine = math.cos(bend_event["yaw"])
                    sine = math.sin(bend_event["yaw"])
                    driver_direction = _normalize((
                        driver_direction[0] * cosine
                        + driver_direction[2] * sine,
                        driver_direction[1],
                        -driver_direction[0] * sine
                        + driver_direction[2] * cosine,
                    ))
                    horizontal_length = math.hypot(
                        driver_direction[0], driver_direction[2]
                    )
                    if horizontal_length > 1e-8 and bend_event["pitch"]:
                        elevation = max(
                            -0.48 * math.pi,
                            min(
                                0.48 * math.pi,
                                math.asin(driver_direction[1])
                                + bend_event["pitch"],
                            ),
                        )
                        horizontal_scale = math.cos(elevation) / horizontal_length
                        driver_direction = _normalize((
                            driver_direction[0] * horizontal_scale,
                            math.sin(elevation),
                            driver_direction[2] * horizontal_scale,
                        ))
                    driver["held_direction"] = driver_direction
                    driver["hold_remaining"] = bend_event["hold"]
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
                driver_change_history.append((direction_change, driver_mass))
                response_index = period - response_delay
                if response_index >= 0:
                    coupled_change, coupled_mass = driver_change_history[response_index]
                else:
                    coupled_change, coupled_mass = ((0.0, 0.0, 0.0), driver_mass)
                counter_direction = _normalize((-load_x, 0.0, -load_z))
                response_weights = []
                for responder in responders:
                    horizontal_direction = _normalize((
                        responder["direction"][0], 0.0,
                        responder["direction"][2],
                    ))
                    alignment = max(0.0, sum(
                        horizontal_direction[axis] * counter_direction[axis]
                        for axis in (0, 2)
                    ))
                    horizontal_lever = math.hypot(
                        responder["position"][0], responder["position"][2]
                    )
                    # A responder is more effective when it already points
                    # toward the counter-moment side and has developed useful
                    # leverage. The floor keeps every sibling responsive.
                    response_weights.append(
                        0.12 + alignment * (1.0 + 0.02 * horizontal_lever)
                    )
                response_weight_sum = sum(response_weights)
                for responder, response_weight in zip(
                    responders, response_weights
                ):
                    response_share = response_weight / response_weight_sum
                    responder["response_share_total"] += response_share
                    responder_previous = responder["direction"]
                    responder_progress = responder["grown"] / responder["steps"]
                    responder_tip = (
                        responder["base_radius"] * responder["tip_ratio"]
                    )
                    responder_r0 = responder["base_radius"] + (
                        responder_tip - responder["base_radius"]
                    ) * responder_progress ** 1.35
                    responder_mass_estimate = (
                        responder_r0 * responder_r0 * step_length
                    )
                    mass_ratio = coupled_mass / max(
                        1e-8, responder_mass_estimate
                    )
                    responder_vertical_deficit = max(
                        0.0, target_vertical - responder_previous[1]
                    )
                    responder_direction = _normalize((
                        momentum * responder_previous[0]
                        + outward_bias * responder["outward"][0]
                        + phototropism * light_direction[0]
                        - coupling * response_share * mass_ratio
                        * coupled_change[0],
                        momentum * responder_previous[1]
                        + outward_bias * responder["outward"][1]
                        + phototropism * light_direction[1]
                        + proprioception * responder_vertical_deficit,
                        momentum * responder_previous[2]
                        + outward_bias * responder["outward"][2]
                        + phototropism * light_direction[2]
                        - coupling * response_share * mass_ratio
                        * coupled_change[2],
                    ))
                    responder_direction = apply_rise_schedule(
                        responder_direction, responder, period
                    )
                    responder_mass, responder_midpoint = grow_pair_segment(
                        responder, responder_direction
                    )
                    load_x += responder_mass * responder_midpoint[0]
                    load_z += responder_mass * responder_midpoint[2]
                    total_mass += responder_mass

            fork_config = coupled_group.get("structural_fork", {})
            fork_states = []
            minimum_parent_periods = int(
                fork_config.get("minimum_parent_periods", group_periods)
            )
            if (
                fork_config.get("enabled", False)
                and group_periods >= minimum_parent_periods
            ):
                continuation_periods = max(1, int(
                    fork_config.get(
                        "continuation_periods",
                        fork_config.get("daughter_periods", 8),
                    )
                ))
                lateral_periods = max(1, int(
                    fork_config.get("lateral_periods", continuation_periods)
                ))
                continuation_angle = math.radians(float(
                    fork_config.get("continuation_angle", 10.0)
                ))
                lateral_angle = math.radians(float(
                    fork_config.get(
                        "lateral_angle", fork_config.get("angle", 36.0)
                    )
                ))
                fork_upward = float(fork_config.get("upward_bias", 0.12))
                continuation_radius_ratio = float(fork_config.get(
                    "continuation_radius_ratio",
                    fork_config.get("radius_ratio", 0.62),
                ))
                lateral_radius_ratio = float(fork_config.get(
                    "lateral_radius_ratio", continuation_radius_ratio
                ))
                lateral_bend_period = max(0, int(
                    fork_config.get("lateral_bend_period", 2)
                ))
                lateral_bend_yaw = math.radians(float(
                    fork_config.get("lateral_bend_yaw", 0.0)
                ))
                lateral_bend_pitch = math.radians(float(
                    fork_config.get("lateral_bend_pitch", 0.0)
                ))
                lateral_horizontal_periods = max(0, int(
                    fork_config.get("lateral_horizontal_periods", 0)
                ))
                intermediate_config = fork_config.get(
                    "intermediate_laterals", {}
                )
                for parent_index, parent in enumerate(states):
                    parent_tip_radius = (
                        parent["base_radius"] * parent["tip_ratio"]
                    )
                    daughter_specs = (
                        (
                            "continuation", -continuation_angle,
                            continuation_periods, continuation_radius_ratio,
                        ),
                        (
                            "lateral", lateral_angle,
                            lateral_periods, lateral_radius_ratio,
                        ),
                    )
                    for role, angle, periods, daughter_radius_ratio in daughter_specs:
                        cosine = math.cos(angle)
                        sine = math.sin(angle)
                        parent_direction = parent["direction"]
                        daughter_direction = _normalize((
                            parent_direction[0] * cosine
                            + parent_direction[2] * sine,
                            parent_direction[1] + fork_upward,
                            -parent_direction[0] * sine
                            + parent_direction[2] * cosine,
                        ))
                        fork_states.append({
                            "name": (
                                f"{parent['name']}_{role}"
                            ),
                            "position": parent["position"],
                            "direction": daughter_direction,
                            "outward": daughter_direction,
                            "base_radius": (
                                parent_tip_radius * daughter_radius_ratio
                            ),
                            "tip_ratio": 0.48,
                            "steps": periods,
                            "role": role,
                            "bend_sign": -1.0 if parent_index % 2 else 1.0,
                            "grown": 0,
                            "mass": 0.0,
                            "trajectory": [],
                        })

                    if intermediate_config.get("enabled", False):
                        attachment_index = min(
                            len(parent["trajectory"]) - 1,
                            parent["lateral_attachment_period"] - 1,
                        )
                        attachment = parent["trajectory"][attachment_index]
                        intermediate_angle = math.radians(float(
                            intermediate_config.get("angle", 72.0)
                        ))
                        intermediate_sign = (
                            -1.0 if parent_index % 2 else 1.0
                        )
                        cosine = math.cos(
                            intermediate_sign * intermediate_angle
                        )
                        sine = math.sin(
                            intermediate_sign * intermediate_angle
                        )
                        attachment_direction = attachment["direction"]
                        intermediate_direction = _normalize((
                            attachment_direction[0] * cosine
                            + attachment_direction[2] * sine,
                            attachment_direction[1],
                            -attachment_direction[0] * sine
                            + attachment_direction[2] * cosine,
                        ))
                        fork_states.append({
                            "name": f"{parent['name']}_intermediate_lateral",
                            "position": attachment["position"],
                            "direction": intermediate_direction,
                            "outward": intermediate_direction,
                            "base_radius": (
                                attachment["radius"] * float(
                                    intermediate_config.get(
                                        "radius_ratio", 0.58
                                    )
                                )
                            ),
                            "tip_ratio": 0.45,
                            "steps": max(1, int(
                                intermediate_config.get("periods", 12)
                            )),
                            "role": "lateral",
                            "bend_sign": -intermediate_sign,
                            "grown": 0,
                            "mass": 0.0,
                            "trajectory": [],
                        })

                daughter_growth_periods = max(
                    daughter["steps"] for daughter in fork_states
                )
                for _ in range(daughter_growth_periods):
                    for daughter in fork_states:
                        if daughter["grown"] >= daughter["steps"]:
                            continue
                        previous = daughter["direction"]
                        vertical_deficit = max(
                            0.0, target_vertical - previous[1]
                        )
                        direction = _normalize((
                            momentum * previous[0]
                            + outward_bias * daughter["outward"][0]
                            + phototropism * light_direction[0],
                            momentum * previous[1]
                            + outward_bias * daughter["outward"][1]
                            + phototropism * light_direction[1]
                            + proprioception * vertical_deficit,
                            momentum * previous[2]
                            + outward_bias * daughter["outward"][2]
                            + phototropism * light_direction[2],
                        ))
                        if (
                            daughter["role"] == "lateral"
                            and daughter["grown"] < lateral_horizontal_periods
                        ):
                            direction = _normalize((
                                direction[0],
                                min(direction[1], horizontal_max_vertical),
                                direction[2],
                            ))
                        if (
                            daughter["role"] == "lateral"
                            and daughter["grown"] == lateral_bend_period
                        ):
                            bend_yaw = (
                                daughter["bend_sign"] * lateral_bend_yaw
                            )
                            cosine = math.cos(bend_yaw)
                            sine = math.sin(bend_yaw)
                            direction = _normalize((
                                direction[0] * cosine
                                + direction[2] * sine,
                                direction[1],
                                -direction[0] * sine
                                + direction[2] * cosine,
                            ))
                            horizontal_length = math.hypot(
                                direction[0], direction[2]
                            )
                            if horizontal_length > 1e-8 and lateral_bend_pitch:
                                elevation = max(
                                    -0.48 * math.pi,
                                    min(
                                        0.48 * math.pi,
                                        math.asin(direction[1])
                                        + lateral_bend_pitch,
                                    ),
                                )
                                horizontal_scale = (
                                    math.cos(elevation) / horizontal_length
                                )
                                direction = _normalize((
                                    direction[0] * horizontal_scale,
                                    math.sin(elevation),
                                    direction[2] * horizontal_scale,
                                ))
                        daughter_mass, daughter_midpoint = grow_pair_segment(
                            daughter, direction
                        )
                        load_x += daughter_mass * daughter_midpoint[0]
                        load_z += daughter_mass * daughter_midpoint[2]
                        total_mass += daughter_mass

            branchlet_config = coupled_group.get("branchlets", {})
            branchlet_axis_count = 0
            if branchlet_config.get("enabled", False) and fork_states:
                branchlet_depth = max(1, int(
                    branchlet_config.get("depth", 2)
                ))
                branchlet_segments = max(2, int(
                    branchlet_config.get("segments_per_axis", 4)
                ))
                branchlet_length = float(
                    branchlet_config.get("length", 16.0)
                )
                branchlet_length_ratio = float(
                    branchlet_config.get("length_ratio", 0.58)
                )
                branchlet_lateral_length_ratio = float(
                    branchlet_config.get("lateral_length_ratio", 0.48)
                )
                branchlet_continuation_ratio = float(
                    branchlet_config.get(
                        "continuation_length_ratio", branchlet_length_ratio
                    )
                )
                branchlet_radius_ratio = float(
                    branchlet_config.get("radius_ratio", 0.42)
                )
                branchlet_divergence = math.radians(float(
                    branchlet_config.get("divergence", 48.0)
                ))
                branchlet_upward = float(
                    branchlet_config.get("upward_bias", 0.30)
                )
                branchlet_jitter = math.radians(float(
                    branchlet_config.get("angle_jitter", 14.0)
                ))
                crownlet_root_axes = max(2, int(
                    branchlet_config.get("crownlet_root_axes", 3)
                ))
                crownlet_spread = math.radians(float(
                    branchlet_config.get("crownlet_spread", 62.0)
                ))
                crownlet_attachment_fractions = tuple(
                    float(value) for value in branchlet_config.get(
                        "crownlet_attachment_fractions", [0.55, 0.75, 0.95]
                    )
                )
                branchlet_lateral_fractions = tuple(
                    float(value) for value in branchlet_config.get(
                        "lateral_attachment_fractions", [0.38, 0.72]
                    )
                )
                crownlet_anchor_roles = set(
                    str(role) for role in branchlet_config.get(
                        "crownlet_anchor_roles", ["continuation"]
                    )
                )
                crownlet_anchor_names = set(
                    str(name) for name in branchlet_config.get(
                        "crownlet_anchor_names", []
                    )
                )
                leaves_enabled = bool(
                    branchlet_config.get("leaves_enabled", False)
                )
                leaves_per_terminal = max(1, int(
                    branchlet_config.get("leaves_per_terminal", 3)
                ))
                leaf_length = float(
                    branchlet_config.get("leaf_length", 4.2)
                )
                leaf_width = float(
                    branchlet_config.get("leaf_width", 1.35)
                )
                crownlet_count = 0
                leaf_count = 0

                def grow_branchlet_axis(
                    start, direction, length, radius, depth, key
                ):
                    nonlocal branchlet_axis_count, leaf_count
                    branchlet_axis_count += 1
                    current = start
                    local_direction = _normalize(direction)
                    step = length / branchlet_segments
                    axis_points = []
                    for segment_index in range(branchlet_segments):
                        progress0 = segment_index / branchlet_segments
                        progress1 = (segment_index + 1) / branchlet_segments
                        side = _normalize(_cross(
                            (0.0, 1.0, 0.0), local_direction
                        ))
                        wander = 0.10 * _noise(
                            key + segment_index * 0.73, seed
                        )
                        local_direction = _normalize((
                            local_direction[0] + wander * side[0],
                            local_direction[1]
                            + branchlet_upward * 0.16,
                            local_direction[2] + wander * side[2],
                        ))
                        end = tuple(
                            current[axis] + local_direction[axis] * step
                            for axis in range(3)
                        )
                        r0 = radius * (1.0 - 0.62 * progress0)
                        r1 = radius * (1.0 - 0.62 * progress1)
                        segments.append(Segment(
                            current, end, r0, r1, "wood"
                        ))
                        current = end
                        axis_points.append((current, local_direction, r1))

                    if depth <= 1:
                        if leaves_enabled:
                            for leaf_index in range(leaves_per_terminal):
                                point_index = min(
                                    len(axis_points) - 1,
                                    round(
                                        leaf_index
                                        * (len(axis_points) - 1)
                                        / max(1, leaves_per_terminal - 1)
                                    ),
                                )
                                leaf_base, leaf_tangent, _ = axis_points[
                                    point_index
                                ]
                                leaf_side = _normalize(_cross(
                                    (0.0, 1.0, 0.0), leaf_tangent
                                ))
                                if sum(
                                    value * value for value in leaf_side
                                ) < 1e-8:
                                    leaf_side = (1.0, 0.0, 0.0)
                                sign = -1.0 if leaf_index % 2 else 1.0
                                leaf_direction = _normalize((
                                    0.35 * leaf_tangent[0]
                                    + sign * leaf_side[0],
                                    0.35 * leaf_tangent[1] + 0.16,
                                    0.35 * leaf_tangent[2]
                                    + sign * leaf_side[2],
                                ))
                                leaf_tip = tuple(
                                    leaf_base[axis]
                                    + leaf_length * leaf_direction[axis]
                                    for axis in range(3)
                                )
                                segments.append(Segment(
                                    leaf_base, leaf_tip,
                                    leaf_width, 0.0, "leaf",
                                ))
                                leaf_count += 1
                        return
                    for child_index, fraction in enumerate(
                        branchlet_lateral_fractions
                    ):
                        point_index = min(
                            len(axis_points) - 1,
                            max(0, round(
                                fraction * (len(axis_points) - 1)
                            )),
                        )
                        child_start, child_tangent, child_parent_radius = (
                            axis_points[point_index]
                        )
                        side = _normalize(_cross(
                            (0.0, 1.0, 0.0), child_tangent
                        ))
                        if sum(value * value for value in side) < 1e-8:
                            side = (1.0, 0.0, 0.0)
                        local_up = _normalize(_cross(child_tangent, side))
                        angle = (
                            branchlet_divergence
                            + branchlet_jitter * _noise(
                                key + child_index * 2.17, seed
                            )
                        )
                        radial_angle = (
                            key * 2.399963229728653
                            + child_index * math.pi * 0.73
                        )
                        radial = _normalize(tuple(
                            math.cos(radial_angle) * side[axis]
                            + math.sin(radial_angle) * local_up[axis]
                            for axis in range(3)
                        ))
                        child_direction = _normalize((
                            child_tangent[0] * math.cos(angle)
                            + radial[0] * math.sin(angle),
                            child_tangent[1] * math.cos(angle)
                            + radial[1] * math.sin(angle)
                            + branchlet_upward,
                            child_tangent[2] * math.cos(angle)
                            + radial[2] * math.sin(angle),
                        ))
                        grow_branchlet_axis(
                            child_start,
                            child_direction,
                            length * branchlet_lateral_length_ratio * (
                                0.88 + 0.20 * _noise(
                                    key + child_index * 3.11, seed
                                )
                            ),
                            child_parent_radius * branchlet_radius_ratio,
                            depth - 1,
                            key * 1.91 + child_index + 1.0,
                        )

                    continuation_side = _normalize(_cross(
                        (0.0, 1.0, 0.0), local_direction
                    ))
                    if sum(
                        value * value for value in continuation_side
                    ) < 1e-8:
                        continuation_side = (1.0, 0.0, 0.0)
                    continuation_turn = 0.35 * branchlet_jitter * _noise(
                        key + 9.7, seed
                    )
                    continuation_direction = _normalize((
                        local_direction[0]
                        + math.sin(continuation_turn)
                        * continuation_side[0],
                        local_direction[1] + branchlet_upward * 0.35,
                        local_direction[2]
                        + math.sin(continuation_turn)
                        * continuation_side[2],
                    ))
                    grow_branchlet_axis(
                        current,
                        continuation_direction,
                        length * branchlet_continuation_ratio,
                        axis_points[-1][2] * branchlet_radius_ratio,
                        depth - 1,
                        key * 2.13 + 7.0,
                    )

                for source_index, source in enumerate(fork_states):
                    if (
                        not source["trajectory"]
                        or source["role"] not in crownlet_anchor_roles
                        or (
                            crownlet_anchor_names
                            and source["name"] not in crownlet_anchor_names
                        )
                    ):
                        continue
                    crownlet_count += 1
                    for root_index in range(crownlet_root_axes):
                        attachment_fraction = crownlet_attachment_fractions[
                            root_index % len(crownlet_attachment_fractions)
                        ]
                        trajectory_index = min(
                            len(source["trajectory"]) - 1,
                            max(0, round(
                                attachment_fraction
                                * (len(source["trajectory"]) - 1)
                            )),
                        )
                        attachment = source["trajectory"][trajectory_index]
                        tangent = attachment["direction"]
                        side = _normalize(_cross(
                            (0.0, 1.0, 0.0), tangent
                        ))
                        if sum(value * value for value in side) < 1e-8:
                            side = (1.0, 0.0, 0.0)
                        local_up = _normalize(_cross(tangent, side))
                        radial_angle = (
                            2.0 * math.pi * root_index / crownlet_root_axes
                            + 0.35 * _noise(source_index + 0.7, seed)
                        )
                        radial = _normalize(tuple(
                            math.cos(radial_angle) * side[axis]
                            + math.sin(radial_angle) * local_up[axis]
                            for axis in range(3)
                        ))
                        spread_angle = 0.5 * crownlet_spread
                        spread_angle += branchlet_jitter * _noise(
                            source_index * 3.7 + root_index, seed
                        )
                        root_lift = branchlet_upward * (
                            0.75 + 0.35 * _noise(
                                source_index * 5.1 + root_index, seed
                            )
                        )
                        initial_direction = _normalize((
                            tangent[0] * math.cos(spread_angle)
                            + radial[0] * math.sin(spread_angle),
                            tangent[1] * math.cos(spread_angle)
                            + radial[1] * math.sin(spread_angle)
                            + root_lift,
                            tangent[2] * math.cos(spread_angle)
                            + radial[2] * math.sin(spread_angle),
                        ))
                        grow_branchlet_axis(
                            attachment["position"],
                            initial_direction,
                            branchlet_length,
                            attachment["radius"] * branchlet_radius_ratio,
                            branchlet_depth,
                            source_index * 11.0 + root_index + 1.0,
                        )

            if balanced.get("report_balance", False):
                center_x = load_x / total_mass if total_mass else 0.0
                center_z = load_z / total_mass if total_mass else 0.0
                print("Coupled scaffold-group growth:")
                for state in states:
                    print(
                        f"  {state['name']}: {state['grown']} periods, "
                        f"mass {state['mass']:.1f}, direction "
                        f"({state['direction'][0]:.3f}, "
                        f"{state['direction'][1]:.3f}, "
                        f"{state['direction'][2]:.3f}), response share "
                        f"{state['response_share_total'] / group_periods:.3f}"
                    )
                if fork_states:
                    print(
                        f"  structural daughters: {len(fork_states)} axes, "
                        f"{continuation_periods} continuation / "
                        f"{lateral_periods} lateral periods"
                    )
                if branchlet_axis_count:
                    print(
                        f"  composite canopy clumps: {crownlet_count}, "
                        f"leaf-bearing axes: {branchlet_axis_count}"
                    )
                    if leaf_count:
                        print(f"  live-oak leaves: {leaf_count}")
                    for source in fork_states:
                        if (
                            source["trajectory"]
                            and source["role"] in crownlet_anchor_roles
                        ):
                            endpoint = source["trajectory"][-1]["position"]
                            print(
                                f"    {source['name']} clump endpoint: "
                                f"({endpoint[0]:.1f}, {endpoint[1]:.1f}, "
                                f"{endpoint[2]:.1f})"
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
