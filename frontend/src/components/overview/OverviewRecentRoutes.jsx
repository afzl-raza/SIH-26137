import React from 'react';
import { Info, MoreVertical } from 'lucide-react';

const ROUTES = [
  { name: 'North Hub → Downtown', meta: '6 stops · 18.4 km', vehicles: 4, dep: '8:20 AM', saved: '22 min', status: 'In progress' },
  { name: 'Airport Loop', meta: '9 stops · 31.2 km', vehicles: 3, dep: '7:45 AM', saved: '34 min', status: 'Optimized' },
  { name: 'Central Depot → Riverside', meta: '4 stops · 12.8 km', vehicles: 2, dep: '7:10 AM', saved: '11 min', status: 'Review' },
  { name: 'Westside Deliveries', meta: '12 stops · 42.6 km', vehicles: 5, dep: '6:30 AM', saved: '48 min', status: 'Optimized' },
  { name: 'Harbor Morning Run', meta: '7 stops · 24.1 km', vehicles: 2, dep: '6:05 AM', saved: '19 min', status: 'Optimized' },
];

const STATUS_STYLE = {
  'In progress': { bg: '#17333B', fg: '#55C7E8' },
  Optimized: { bg: '#173A2D', fg: '#43D493' },
  Review: { bg: '#462122', fg: '#FF6868' },
};

// Same illustrative-data caveat as the rest of this page - a fixed list
// matching the approved design, not a real run history query.
export default function OverviewRecentRoutes() {
  return (
    <div className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-5">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <h2 className="font-display font-bold text-[15px] text-[#FFF9F1]">Recent routes</h2>
          <Info size={12} className="text-[#817970]" />
        </div>
        <button className="text-[11px] text-[#FF7A1A] font-semibold cursor-default">View all routes</button>
      </div>
      <p className="text-[11px] text-[#817970] mb-4">The latest plans created by your team.</p>

      <div className="overflow-x-auto -mx-1">
        <table className="w-full text-[12px] min-w-[560px]">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-[#817970] border-b border-[#3B342A]">
              <th className="text-left font-semibold px-1 pb-2">Route</th>
              <th className="text-left font-semibold px-1 pb-2">Vehicles</th>
              <th className="text-left font-semibold px-1 pb-2">Departure</th>
              <th className="text-left font-semibold px-1 pb-2">Saved</th>
              <th className="text-left font-semibold px-1 pb-2">Status</th>
              <th className="w-6" />
            </tr>
          </thead>
          <tbody>
            {ROUTES.map(r => {
              const st = STATUS_STYLE[r.status];
              return (
                <tr key={r.name} className="border-b border-[#2A2620] last:border-0">
                  <td className="px-1 py-2.5">
                    <div className="text-[#FFF9F1] font-semibold">{r.name}</div>
                    <div className="text-[10px] text-[#817970]">{r.meta}</div>
                  </td>
                  <td className="px-1 text-[#B9B0A5]">{r.vehicles}</td>
                  <td className="px-1 text-[#B9B0A5]">{r.dep}</td>
                  <td className="px-1 font-semibold text-[#43D493]">{r.saved}</td>
                  <td className="px-1">
                    <span className="text-[10px] font-semibold rounded-full px-2 py-0.5" style={{ backgroundColor: st.bg, color: st.fg }}>
                      {r.status}
                    </span>
                  </td>
                  <td className="px-1 text-[#817970] cursor-default"><MoreVertical size={14} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
