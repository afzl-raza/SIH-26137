import React from 'react';
import { MapPin, Route, Truck, CloudRain } from 'lucide-react';
import SectionHeader from './SectionHeader';

// Secondary metadata - deliberately placed at the bottom of the page, not
// the top, so the story leads with the result rather than the setup.
export default function ScenarioDetails({ scenario, networkMeta, trafficMode, weatherEnabled }) {
  const studyArea = networkMeta?.dataSource === 'openstreetmap'
    ? (networkMeta.location?.display_name || 'OpenStreetMap area')
    : 'Synthetic';
  const nodeCount = networkMeta?.nodeCount;
  const edgeCount = networkMeta?.edgeCount ?? scenario?.edges?.length;

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-3">
      <SectionHeader icon={MapPin} title="Scenario Details" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat label="Study Area" value={studyArea} icon={MapPin} truncate />
        <Stat label="Network" value={nodeCount != null ? `${nodeCount} nodes` : '—'} sub={edgeCount != null ? `${edgeCount} road segments` : undefined} icon={Route} />
        <Stat label="Vehicles" value={scenario.vehicles?.length ?? 0} icon={Truck} />
        <Stat label="Stops" value={scenario.jobs?.length ?? 0} icon={MapPin} />
        <Stat label="Traffic" value={trafficMode ? trafficMode[0].toUpperCase() + trafficMode.slice(1) : '—'} icon={CloudRain} />
        <Stat label="Weather" value={weatherEnabled ? 'Enabled' : 'Disabled'} icon={CloudRain} />
      </div>
    </div>
  );
}

function Stat({ label, value, sub, icon: Icon, truncate }) {
  return (
    <div className="clean-card p-3 rounded-lg flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-gray-500 text-[10px] uppercase tracking-wider font-semibold">
        {Icon && <Icon size={11} />}
        {label}
      </div>
      <div className={`font-display text-base font-bold text-white ${truncate ? 'truncate' : ''}`} title={truncate ? String(value) : undefined}>
        {value}
      </div>
      {sub && <div className="text-[10px] text-gray-500 font-mono">{sub}</div>}
    </div>
  );
}
