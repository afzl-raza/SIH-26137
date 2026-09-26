import React from 'react';
import { TrendingUp, Info, Plus, Minus, Navigation2 } from 'lucide-react';

// Purely decorative - a static illustration of "a map like this exists",
// not the real Leaflet map (that's one click away, in the real Dashboard).
// Deliberately drawn as an abstract grid rather than real tiles/geometry so
// it never reads as an actual place or a live vehicle position.
const VEHICLES = [
  { id: 'V-005', x: '68%', y: '22%' },
  { id: 'V-008', x: '48%', y: '38%' },
  { id: 'V-014', x: '18%', y: '55%' },
  { id: 'V-021', x: '58%', y: '68%' },
];

export default function OverviewLiveMap() {
  return (
    <div className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-5 flex flex-col">
      <div className="flex items-start justify-between mb-1 flex-wrap gap-2">
        <div>
          <div className="flex items-center gap-1.5">
            <h2 className="font-display font-bold text-[15px] text-[#FFF9F1]">Live traffic map</h2>
            <Info size={12} className="text-[#817970]" />
          </div>
          <p className="text-[11px] text-[#817970] mt-0.5">
            See vehicle positions and traffic-aware routes in real time.
          </p>
        </div>
        <span className="flex items-center gap-1.5 text-[10px] font-semibold text-[#43D493] bg-[#173A2D] rounded-full px-2.5 py-1">
          <span className="w-1.5 h-1.5 rounded-full bg-[#43D493]" />
          Live · updated now
        </span>
      </div>

      <div
        title="Illustrative map - not the real live view"
        className="relative mt-3 rounded-xl overflow-hidden bg-[#100F0D] border border-[#3B342A] h-[280px] cursor-default"
        style={{
          backgroundImage:
            'linear-gradient(#211E1A 1px, transparent 1px), linear-gradient(90deg, #211E1A 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }}
      >
        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          <path d="M 18 55 Q 40 30 68 22" fill="none" stroke="#FF7A1A" strokeWidth="0.6" />
          <path d="M 18 55 Q 40 65 58 68" fill="none" stroke="#55C7E8" strokeWidth="0.5" strokeDasharray="1.5,1.5" />
          <path d="M 48 38 Q 55 50 58 68" fill="none" stroke="#A98AFF" strokeWidth="0.5" strokeDasharray="1.5,1.5" />
        </svg>

        {VEHICLES.map(v => (
          <div
            key={v.id}
            className="absolute -translate-x-1/2 -translate-y-1/2 flex items-center gap-1 bg-[#171512] border border-[#3B342A] rounded-full px-2 py-0.5 text-[9px] font-semibold text-[#FFF9F1] whitespace-nowrap"
            style={{ left: v.x, top: v.y }}
          >
            <Navigation2 size={9} className="text-[#FF7A1A]" />
            {v.id}
          </div>
        ))}

        <div className="absolute left-[30%] top-[42%] -translate-x-1/2 -translate-y-1/2 bg-[#462122] text-[#FF6868] text-[9px] font-semibold rounded-full px-2 py-0.5 whitespace-nowrap">
          8 min delay
        </div>

        <div className="absolute bottom-2 left-2 text-[9px] text-[#817970] bg-[#171512]/80 rounded px-1.5 py-0.5">
          Traffic refreshed 12 sec ago
        </div>
        <div className="absolute top-2 right-2 flex flex-col gap-1">
          <button className="w-6 h-6 rounded bg-[#171512] border border-[#3B342A] text-[#B9B0A5] flex items-center justify-center cursor-default">
            <Plus size={12} />
          </button>
          <button className="w-6 h-6 rounded bg-[#171512] border border-[#3B342A] text-[#B9B0A5] flex items-center justify-center cursor-default">
            <Minus size={12} />
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
        <div className="flex items-center gap-3 text-[10px] text-[#B9B0A5]">
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#FF7A1A] inline-block" /> Recommended route</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#55C7E8] inline-block" style={{ borderTop: '1px dashed #55C7E8' }} /> Alternate route</span>
          <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#A98AFF] inline-block" /> Return route</span>
        </div>
        <button className="flex items-center gap-1 text-[11px] text-[#FF7A1A] font-semibold cursor-default">
          <TrendingUp size={12} />
          Open full map →
        </button>
      </div>
    </div>
  );
}
