import math
from typing import List, Optional
from .schema import EdgeAttrs, NodeAttrs


def bpr_travel_time(
    t0: float,
    volume: float,
    capacity: float,
    alpha: float = 0.15,
    beta: float = 4.0
) -> float:
    """
    Bureau of Public Roads (BPR) link travel time function:
    t(v) = t0 * (1 + alpha * (v / c)^beta)
    """
    if t0 <= 0:
        return 0.0
    c = max(1.0, capacity)
    v = max(0.0, volume)
    saturation = v / c
    return t0 * (1.0 + alpha * (saturation ** beta))


def webster_delay(
    cycle_s: float,
    green_ratio: float,
    volume: float,
    capacity: float
) -> float:
    """
    Webster's Delay Formula for signalized intersection delay:
    d_intersection = C * (1 - lambda)^2 / (2 * (1 - lambda * x))
    where C = cycle_s, lambda = green_ratio, x = v / c saturation degree.
    """
    if cycle_s <= 0 or green_ratio <= 0 or green_ratio >= 1.0:
        return 0.0

    c = max(1.0, capacity)
    v = max(0.0, volume)
    x = v / c  # degree of saturation

    denom = 2.0 * (1.0 - green_ratio * min(x, 0.99))
    if denom <= 0.01:
        return cycle_s * 3.0  # Max queuing delay bound

    numerator = cycle_s * ((1.0 - green_ratio) ** 2)
    delay = numerator / denom
    return max(0.0, min(delay, cycle_s * 5.0))


def composite_edge_weight(
    edge: EdgeAttrs,
    target_node: Optional[NodeAttrs] = None,
    prev_node: Optional[NodeAttrs] = None,
    next_node: Optional[NodeAttrs] = None,
    time_of_day_hour: Optional[float] = None,
    w_time: float = 1.0,
    w_dist: float = 0.5,
    w_fuel: float = 0.2,
    w_emissions: float = 0.1
) -> float:
    """
    Composite multi-objective link cost:
    W(e) = w_time * t(v) + w_dist * d + w_fuel * Fuel + w_emissions * Emissions + Webster_Delay + Turn_Penalty
    If blocked or impassable incident, returns 1e9 (infinity).
    """
    if edge.is_blocked or edge.incident_severity >= 1.0:
        return 1e9

    # 1. Apply time-of-day multiplier if specified
    vol = edge.volume_vph
    if time_of_day_hour is not None:
        vol *= get_time_of_day_multiplier(time_of_day_hour)

    # 2. BPR link travel time in seconds
    t0 = edge.free_flow_travel_time_s
    cap = edge.capacity_vph
    t_bpr = bpr_travel_time(t0, vol, cap, alpha=edge.alpha, beta=edge.beta)

    # 3. Webster signal delay if target node is signalized
    t_signal = 0.0
    if target_node:
        t_signal = webster_delay(target_node.signal_cycle_s, target_node.green_ratio, vol, cap)

    # 4. Turn delay penalty (straight, left, right, U-turn)
    t_turn = 0.0
    if prev_node and target_node and next_node:
        t_turn = calculate_turn_penalty(prev_node, target_node, next_node)

    total_time_s = t_bpr + t_signal + t_turn

    # 5. Distance in kilometers
    dist_km = edge.length_m / 1000.0

    # 6. Fuel & emissions models based on distance and congestion factor
    saturation = max(0.0, vol / max(1.0, cap))
    fuel_liters = dist_km * 0.08 * (1.0 + 0.5 * (saturation ** 2))  # Base ~8L/100km
    emissions_kg = fuel_liters * 2.31                               # ~2.31 kg CO2 per liter

    # 7. Composite cost
    cost = (
        w_time * total_time_s +
        w_dist * dist_km +
        w_fuel * fuel_liters +
        w_emissions * emissions_kg
    )
    return max(0.01, round(cost, 4))


def calculate_turn_penalty(
    prev_node: Optional[NodeAttrs],
    curr_node: NodeAttrs,
    next_node: Optional[NodeAttrs],
    drive_on_left: bool = True
) -> float:
    """
    Directional turn penalty based on geometric vectors:
    - Straight (|angle| <= 25 deg): 0.0s
    - Left turn (drive-on-left): 3.0s
    - Right turn (across oncoming traffic): 12.0s
    - U-turn (|angle| > 135 deg): 25.0s
    """
    if not prev_node or not next_node:
        return 0.0

    v1_x = curr_node.lng - prev_node.lng
    v1_y = curr_node.lat - prev_node.lat
    v2_x = next_node.lng - curr_node.lng
    v2_y = next_node.lat - curr_node.lat

    angle1 = math.atan2(v1_y, v1_x)
    angle2 = math.atan2(v2_y, v2_x)

    diff_deg = math.degrees(angle2 - angle1)
    while diff_deg > 180.0:
        diff_deg -= 360.0
    while diff_deg <= -180.0:
        diff_deg += 360.0

    abs_diff = abs(diff_deg)
    if abs_diff <= 25.0:
        return 0.0
    elif abs_diff > 135.0:
        return 25.0

    if drive_on_left:
        return 3.0 if diff_deg < 0 else 12.0
    else:
        return 3.0 if diff_deg > 0 else 12.0


def get_time_of_day_multiplier(hour_of_day: float) -> float:
    """
    Diurnal traffic multipliers for peak/off-peak rush hours:
    - 07:30 - 10:00 (Morning Peak): 1.75x
    - 11:00 - 16:00 (Midday): 1.15x
    - 17:00 - 20:30 (Evening Peak): 2.0x
    - 22:00 - 05:00 (Night): 0.5x
    """
    h = hour_of_day % 24.0
    if 7.5 <= h <= 10.0:
        return 1.75
    elif 17.0 <= h <= 20.5:
        return 2.0
    elif 11.0 <= h <= 16.0:
        return 1.15
    elif 22.0 <= h or h <= 5.0:
        return 0.5
    return 1.0


def fifo_safeguard(
    travel_times_over_time: List[float],
    time_slice_step_s: float = 10.0
) -> List[float]:
    """
    Ensures First-In, First-Out (FIFO) consistency over time slices.
    Arrival time A(t_k) = t_k + T(t_k) must be non-decreasing:
    A(t_{k+1}) >= A(t_k) => t_{k+1} + T(t_{k+1}) >= t_k + T(t_k).
    Adjusts T(t_{k+1}) if an overtaking violation occurs.
    """
    if not travel_times_over_time:
        return []

    corrected = list(travel_times_over_time)
    for k in range(len(corrected) - 1):
        t_k = k * time_slice_step_s
        t_next = (k + 1) * time_slice_step_s
        arrival_k = t_k + corrected[k]

        arrival_next = t_next + corrected[k + 1]
        if arrival_next < arrival_k:
            # Adjust travel time at k+1 to prevent overtaking
            corrected[k + 1] = max(0.0, arrival_k - t_next)

    return corrected


def moving_average_smoother(
    volumes: List[float],
    window_size: int = 3
) -> List[float]:
    """
    Causal moving-average volume smoother to prevent high-frequency oscillations in dynamic updates.
    """
    if not volumes:
        return []
    smoothed = []
    for i in range(len(volumes)):
        start_idx = max(0, i - window_size + 1)
        chunk = volumes[start_idx:i + 1]
        smoothed.append(sum(chunk) / len(chunk))
    return smoothed
