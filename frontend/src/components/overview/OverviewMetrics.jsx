import React from 'react';
import { Truck, Clock, CalendarCheck, Activity, Info } from 'lucide-react';

// Fixed illustrative values matching the approved design exactly. Unlike
// every other number in this app, these are NOT read from the backend -
// this prototype has no fleet telemetry, schedule tracking, or live traffic
// feed to back them with. Each card carries an explicit "Example data" mark
// so it never reads as a live figure.
const METRICS = [
  {
    icon: Truck, label: 'Vehicles moving', value: '18', accent: '#5D7A9E',
    detail: 'of 24 active today', tag: '3 waiting',
  },
  {
    icon: Clock, label: 'Time saved today', value: '3h 42m', accent: '#43D493',
    detail: 'compared with usual routes', tag: '+28 min this hour',
  },
  {
    icon: CalendarCheck, label: 'Routes on schedule', value: '92%', accent: '#F5B942',
    detail: 'arriving within 5 minutes', tag: '2 need attention',
  },
  {
    icon: Activity, label: 'Traffic conditions', value: 'Moderate', accent: '#FF7A1A',
    detail: 'across your operating area', tag: 'Rush hour in 45 min',
  },
];

export default function OverviewMetrics() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {METRICS.map(m => (
        <div key={m.label} className="bg-[#211E1A] border border-[#3B342A] rounded-xl p-4 relative">
          <div
            title="Example data - not a live feed in this prototype"
            className="absolute top-2 right-2 text-[8px] font-bold uppercase tracking-wider text-[#817970] bg-[#171512] border border-[#3B342A] rounded px-1.5 py-0.5 flex items-center gap-1"
          >
            <Info size={9} />
            Example
          </div>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${m.accent}22`, color: m.accent }}>
              <m.icon size={14} />
            </div>
            <span className="text-[11px] text-[#B9B0A5]">{m.label}</span>
          </div>
          <div className="font-display font-bold text-[26px] text-[#FFF9F1] leading-none mb-1.5">
            {m.value}
          </div>
          <div className="text-[10px] text-[#817970]">{m.detail}</div>
          <div className="text-[10px] mt-1" style={{ color: m.accent }}>{m.tag}</div>
        </div>
      ))}
    </div>
  );
}
