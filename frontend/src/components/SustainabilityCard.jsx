import React, { useEffect, useState } from 'react';
import { Leaf, Info } from 'lucide-react';
import { apiFetch } from '../api';

// Estimated fuel and CO2 avoided versus Greedy routing on the same scenario.
// Every figure comes from POST /api/sustainability (backend/sustainability.py),
// which runs a real Greedy baseline and returns the assumptions it used. This
// component only displays them - and always labels them as an estimate.
export default function SustainabilityCard({ scenarioId, result, config }) {
  const [estimate, setEstimate] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!scenarioId || !result) {
      setEstimate(null);
      setFailed(false);
      return undefined;
    }
    let cancelled = false;
    setFailed(false);
    apiFetch('/api/sustainability', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario_id: scenarioId,
        config,
        optimized_distance_km: result.total_distance
      })
    })
      .then(res => (res.ok ? res.json() : Promise.reject(new Error('estimate failed'))))
      .then(json => { if (!cancelled) setEstimate(json); })
      .catch(() => { if (!cancelled) { setEstimate(null); setFailed(true); } });
    return () => { cancelled = true; };
    // A new result is the only trigger: the baseline is tied to that run.
  }, [scenarioId, result]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!result || failed || !estimate) return null;

  const saved = estimate.km_saved;
  const better = saved > 0;
  const fmt = (n) => Math.abs(n).toFixed(1);

  return (
    <div className="clean-card p-3.5 rounded-xl border border-[#3A342E] space-y-2.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-semibold text-gray-300 uppercase tracking-wider">
          <Leaf size={14} className="text-[#6B9A57]" />
          Sustainability
        </div>
        <span className="text-[9px] font-mono text-[#E8C578] px-2 py-0.5 rounded border border-[#5A4A22] bg-[#3A2E14]/50">
          ESTIMATE
        </span>
      </div>

      {better ? (
        <div className="grid grid-cols-3 gap-2">
          <div>
            <div className="font-display text-xl font-bold text-gray-100 tabular-nums">{fmt(saved)} km</div>
            <div className="text-[10px] text-gray-500">fewer km vs Greedy ({estimate.pct_km_saved.toFixed(1)}%)</div>
          </div>
          <div>
            <div className="font-display text-xl font-bold text-gray-100 tabular-nums">{fmt(estimate.fuel_l_saved)} L</div>
            <div className="text-[10px] text-gray-500">diesel avoided</div>
          </div>
          <div>
            <div className="font-display text-xl font-bold text-[#6B9A57] tabular-nums">{fmt(estimate.co2_kg_saved)} kg</div>
            <div className="text-[10px] text-gray-500">CO₂ avoided</div>
          </div>
        </div>
      ) : (
        <p className="text-[11px] text-gray-400 leading-snug">
          This plan drives {fmt(saved)} km {saved < 0 ? 'more' : 'the same'} than Greedy routing
          ({estimate.baseline_km} km → {estimate.optimized_km} km). The objective also weighs travel time and
          congestion, so it does not always minimise distance. No fuel saving is claimed for this run.
        </p>
      )}

      <p className="flex items-start gap-1.5 text-[9px] text-gray-600 leading-snug">
        <Info size={10} className="flex-shrink-0 mt-px" />
        <span>
          {estimate.baseline_km} km (Greedy) → {estimate.optimized_km} km (this plan), one run of this scenario.
          Assumes a {estimate.assumed_vehicle} at {estimate.fuel_l_per_100km} L/100 km and {estimate.co2_kg_per_litre} kg CO₂ per
          litre of diesel. Real savings depend on vehicle, load, speed and traffic.
        </span>
      </p>
    </div>
  );
}
