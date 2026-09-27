import React, { useState, useCallback, useEffect } from 'react';
import OverviewSidebar from '../components/overview/OverviewSidebar';
import OverviewTopBar from '../components/overview/OverviewTopBar';
import OverviewGreeting from '../components/overview/OverviewGreeting';
import OverviewMetrics from '../components/overview/OverviewMetrics';
import OverviewLiveMap from '../components/overview/OverviewLiveMap';
import OverviewAlerts from '../components/overview/OverviewAlerts';
import OverviewRecentRoutes from '../components/overview/OverviewRecentRoutes';
import OverviewActivity from '../components/overview/OverviewActivity';
import { apiFetch } from '../api';

const OPTIMIZE_CONFIG = { algorithm: 'qpso', population_size: 40, max_iterations: 100, seed: 42 };
// A fast, real second opinion purely to give the non-technical summary
// something concrete to compare against ("N% better than simple
// dispatch") - Greedy has no search loop, so this costs single-digit
// milliseconds next to the real optimize call, not a second slow run.
const BASELINE_CONFIG = { algorithm: 'greedy', seed: 42 };

// The operator's home screen - a gate in front of the real algorithm
// workflow (Dashboard.jsx), not a replacement of it. "Today at a glance",
// the live map, the disrupt-a-road interaction, and the alerts/recent-routes
// feeds are all backed by real /api/problem/generate + /api/optimize +
// /api/traffic/update calls - the same endpoints Dashboard.jsx uses - not
// fabricated numbers. Only the workspace switcher and onboarding checklist
// stay decorative, since there is no real multi-user or run-history backend
// behind this prototype beyond the real auth session.
export default function Overview({ onEnterDashboard, onExitToLanding, user, isGuest, onLogout }) {
  const [scenarioId, setScenarioId] = useState(null);
  const [scenario, setScenario] = useState(null);
  const [result, setResult] = useState(null);
  // The Greedy (nearest-stop) baseline on the exact same scenario - real,
  // not invented - used only to state "N% more efficient than simple
  // dispatch" in plain language. Never shown as if it were the chosen plan.
  const [baseline, setBaseline] = useState(null);
  const [loading, setLoading] = useState(true);
  // Set only while re-optimizing after a disruption, so the map/metrics
  // stay visible (not replaced by a full loading skeleton) during the
  // brief recompute.
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const runOptimizeAndBaseline = useCallback(async (id) => {
    const [optRes, baseRes] = await Promise.all([
      apiFetch('/api/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: id, config: OPTIMIZE_CONFIG }),
        timeoutMs: 30000
      }),
      apiFetch('/api/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: id, config: BASELINE_CONFIG }),
        timeoutMs: 30000
      })
    ]);
    if (!optRes.ok) throw new Error('Failed to optimize today\'s scenario');
    if (!baseRes.ok) throw new Error('Failed to compute the comparison baseline');
    const [optData, baseData] = await Promise.all([optRes.json(), baseRes.json()]);
    return { optData, baseData };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const genRes = await apiFetch('/api/problem/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source: 'synthetic', num_nodes: 30, num_jobs: 15, num_vehicles: 3, seed: 42 }),
          timeoutMs: 30000
        });
        if (!genRes.ok) throw new Error('Failed to generate today\'s scenario');
        const genData = await genRes.json();
        if (cancelled) return;
        setScenario(genData.scenario);
        setScenarioId(genData.scenario_id);

        const { optData, baseData } = await runOptimizeAndBaseline(genData.scenario_id);
        if (cancelled) return;
        setResult(optData);
        setBaseline(baseData);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [runOptimizeAndBaseline]);

  // Real disrupt-a-road interaction, same underlying call Dashboard.jsx
  // uses (POST /api/traffic/update with traffic_factor: 1.0 clearing an
  // existing incident) - then both the shown plan and the baseline are
  // re-optimized against the new edge costs, so the "N% more efficient"
  // comparison never goes stale relative to what's on screen.
  const handleDisruptEdge = useCallback(async (source, destination, factor) => {
    if (!scenarioId) return;
    setRefreshing(true);
    setError(null);
    try {
      const trafficRes = await apiFetch('/api/traffic/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId, updates: [{ source, destination, traffic_factor: factor }] }),
        timeoutMs: 30000
      });
      if (!trafficRes.ok) throw new Error('Failed to update road conditions');
      const trafficData = await trafficRes.json();
      setScenario(trafficData.scenario);

      const { optData, baseData } = await runOptimizeAndBaseline(scenarioId);
      setResult(optData);
      setBaseline(baseData);
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  }, [scenarioId, runOptimizeAndBaseline]);

  return (
    <div className="min-h-screen flex bg-[#171512] text-[#FFF9F1] font-sans">
      <OverviewSidebar />

      <div className="flex-1 flex flex-col min-w-0">
        <OverviewTopBar user={user} isGuest={isGuest} onLogout={onLogout} />

        <main className="flex-1 p-6 flex flex-col gap-5 max-w-[1600px] w-full mx-auto">
          {onExitToLanding && (
            <button
              onClick={onExitToLanding}
              className="self-start text-[11px] text-[#817970] hover:text-[#FFF9F1] transition-colors -mb-1"
            >
              ← Back to landing page
            </button>
          )}

          <OverviewGreeting onEnterDashboard={onEnterDashboard} user={user} isGuest={isGuest} />
          <OverviewMetrics scenario={scenario} result={result} baseline={baseline} loading={loading} error={error} />

          <div className="grid grid-cols-1 xl:grid-cols-[1fr,340px] gap-5">
            <OverviewLiveMap
              scenario={scenario}
              scenarioId={scenarioId}
              result={result}
              loading={loading}
              refreshing={refreshing}
              error={error}
              onDisruptEdge={handleDisruptEdge}
            />
            <OverviewAlerts scenario={scenario} result={result} loading={loading} error={error} />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-[1fr,340px] gap-5">
            <OverviewRecentRoutes scenario={scenario} result={result} loading={loading} error={error} />
            <OverviewActivity scenario={scenario} result={result} loading={loading} error={error} />
          </div>
        </main>
      </div>
    </div>
  );
}
