"""
sustainability.py
-----------------
A transparent, labelled ESTIMATE of the fuel and CO2 avoided when the
optimized routes drive fewer kilometres than a naive baseline (Greedy
nearest-stop routing on the same scenario and road conditions).

This is deliberately simple arithmetic on the real route distances the
solvers already report, times two stated emission assumptions. It is not a
measurement: real consumption depends on the vehicle, load, speed and
congestion. The assumptions are returned with every estimate so the UI can
show them next to the number, and so a reader can recompute it by hand.
"""
from dataclasses import dataclass, asdict

# Assumed light commercial diesel van. Fuel use ~9 L/100 km is a typical
# real-world figure for a loaded diesel delivery van; 2.68 kg CO2 per litre
# of diesel is the standard tailpipe emission factor (DEFRA / IPCC).
FUEL_L_PER_100KM = 9.0
CO2_KG_PER_LITRE_DIESEL = 2.68
ASSUMED_VEHICLE = "light commercial diesel van"


@dataclass(frozen=True)
class SustainabilityEstimate:
    baseline_km: float
    optimized_km: float
    km_saved: float          # negative when the optimized plan drives MORE km
    pct_km_saved: float
    fuel_l_saved: float
    co2_kg_saved: float
    assumed_vehicle: str
    fuel_l_per_100km: float
    co2_kg_per_litre: float
    is_estimate: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


def estimate_savings(
    baseline_km: float,
    optimized_km: float,
    fuel_l_per_100km: float = FUEL_L_PER_100KM,
    co2_kg_per_litre: float = CO2_KG_PER_LITRE_DIESEL,
) -> SustainabilityEstimate:
    """Fuel and CO2 difference between a baseline plan and an optimized one.

    Savings are signed: if the optimized plan is longer than the baseline
    (the objective also weighs time and congestion, so this can happen) the
    result is negative rather than clamped to zero.
    """
    if baseline_km < 0 or optimized_km < 0:
        raise ValueError("Distances must be non-negative.")
    km_saved = baseline_km - optimized_km
    fuel_l_saved = km_saved * fuel_l_per_100km / 100.0
    return SustainabilityEstimate(
        baseline_km=round(baseline_km, 2),
        optimized_km=round(optimized_km, 2),
        km_saved=round(km_saved, 2),
        pct_km_saved=round(km_saved / baseline_km * 100.0, 2) if baseline_km > 0 else 0.0,
        fuel_l_saved=round(fuel_l_saved, 2),
        co2_kg_saved=round(fuel_l_saved * co2_kg_per_litre, 2),
        assumed_vehicle=ASSUMED_VEHICLE,
        fuel_l_per_100km=fuel_l_per_100km,
        co2_kg_per_litre=co2_kg_per_litre,
    )
