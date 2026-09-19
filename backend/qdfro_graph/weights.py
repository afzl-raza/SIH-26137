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
    w_time: float = 1.0,
    w_dist: float = 0.5,
    w_fuel: float = 0.2,
    w_emissions: float = 0.1
) -> float:
    """
    Composite multi-objective link cost:
    W(e) = w_time * t(v) + w_dist * d + w_fuel * Fuel + w_emissions * Emissions + Webster_Delay
    If blocked or impassable incident, returns 1e9 (infinity).
    """
    if edge.is_blocked or edge.incident_severity >= 1.0:
        return 1e9

    # 1. BPR link travel time in seconds
    t0 = edge.free_flow_travel_time_s
    vol = edge.volume_vph
    cap = edge.capacity_vph
    t_bpr = bpr_travel_time(t0, vol, cap, alpha=edge.alpha, beta=edge.beta)

    # 2. Webster signal delay if target node is signalized
    t_signal = 0.0
    if target_node:
        t_signal = webster_delay(target_node.signal_cycle_s, target_node.green_ratio, vol, cap)

    total_time_s = t_bpr + t_signal

    # 3. Distance in kilometers
    dist_km = edge.length_m / 1000.0

    # 4. Fuel & emissions models based on distance and congestion factor
    saturation = max(0.0, vol / max(1.0, cap))
    fuel_liters = dist_km * 0.08 * (1.0 + 0.5 * (saturation ** 2))  # Base ~8L/100km
    emissions_kg = fuel_liters * 2.31                               # ~2.31 kg CO2 per liter

    # 5. Composite cost
    cost = (
        w_time * total_time_s +
        w_dist * dist_km +
        w_fuel * fuel_liters +
        w_emissions * emissions_kg
    )
    return max(0.01, round(cost, 4))


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
