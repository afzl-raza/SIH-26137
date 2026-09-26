import React, { useState, useEffect } from 'react';
import OverviewSidebar from '../components/overview/OverviewSidebar';
import OverviewTopBar from '../components/overview/OverviewTopBar';
import OverviewGreeting from '../components/overview/OverviewGreeting';
import OverviewMetrics from '../components/overview/OverviewMetrics';
import OverviewLiveMap from '../components/overview/OverviewLiveMap';
import OverviewAlerts from '../components/overview/OverviewAlerts';
import OverviewRecentRoutes from '../components/overview/OverviewRecentRoutes';
import OverviewActivity from '../components/overview/OverviewActivity';
import { apiFetch } from '../api';

// The operator's home screen - a gate in front of the real algorithm
// workflow (Dashboard.jsx), not a replacement of it. "Today at a glance"
// and the live map are backed by a real, independent generate+optimize run
// against the same /api/problem/generate + /api/optimize endpoints
// Dashboard uses (default synthetic shape, default QPSO+LS config) - not
// fabricated numbers. The SaaS-shell chrome around them (workspace
// switcher, onboarding checklist, alerts/recent-routes/activity feeds)
// stays decorative, since there is no real multi-user or run-history
// backend behind this prototype.
export default function Overview({ onEnterDashboard, onExitToLanding }) {
  const [scenario, setScenario] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

        const optRes = await apiFetch('/api/optimize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            scenario_id: genData.scenario_id,
            config: { algorithm: 'qpso', population_size: 40, max_iterations: 100, seed: 42 }
          }),
          timeoutMs: 30000
        });
        if (!optRes.ok) throw new Error('Failed to optimize today\'s scenario');
        const optData = await optRes.json();
        if (cancelled) return;
        setResult(optData);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="min-h-screen flex bg-[#171512] text-[#FFF9F1] font-sans">
      <OverviewSidebar />

      <div className="flex-1 flex flex-col min-w-0">
        <OverviewTopBar />

        <main className="flex-1 p-6 flex flex-col gap-5 max-w-[1600px] w-full mx-auto">
          {onExitToLanding && (
            <button
              onClick={onExitToLanding}
              className="self-start text-[11px] text-[#817970] hover:text-[#FFF9F1] transition-colors -mb-1"
            >
              ← Back to landing page
            </button>
          )}

          <OverviewGreeting onEnterDashboard={onEnterDashboard} />
          <OverviewMetrics scenario={scenario} result={result} loading={loading} error={error} />

          <div className="grid grid-cols-1 xl:grid-cols-[1fr,340px] gap-5">
            <OverviewLiveMap scenario={scenario} result={result} loading={loading} error={error} />
            <OverviewAlerts />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-[1fr,340px] gap-5">
            <OverviewRecentRoutes />
            <OverviewActivity />
          </div>
        </main>
      </div>
    </div>
  );
}
