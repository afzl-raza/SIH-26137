import React from 'react';
import OverviewSidebar from '../components/overview/OverviewSidebar';
import OverviewTopBar from '../components/overview/OverviewTopBar';
import OverviewGreeting from '../components/overview/OverviewGreeting';
import OverviewMetrics from '../components/overview/OverviewMetrics';
import OverviewLiveMap from '../components/overview/OverviewLiveMap';
import OverviewAlerts from '../components/overview/OverviewAlerts';
import OverviewRecentRoutes from '../components/overview/OverviewRecentRoutes';
import OverviewActivity from '../components/overview/OverviewActivity';

// The operator's home screen - a gate in front of the real algorithm
// workflow (Dashboard.jsx), not a replacement of it. Everything here is
// visual chrome/illustrative data (approved scope), except navigation:
// "Plan your first route" and the 3-step cards are the only real actions,
// and they lead to the actual map/optimize/benchmark workflow.
export default function Overview({ onEnterDashboard, onExitToLanding }) {
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
          <OverviewMetrics />

          <div className="grid grid-cols-1 xl:grid-cols-[1fr,340px] gap-5">
            <OverviewLiveMap />
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
