import React from 'react';
import { Info, Zap, UserPlus, Navigation, CheckCircle2, Leaf } from 'lucide-react';

const EVENTS = [
  { icon: Zap, tone: '#5D7A9E', title: 'Airport Loop was optimized', when: 'Saved 34 minutes · 4 min ago' },
  { icon: UserPlus, tone: '#A98AFF', title: 'Priya joined Metro operations', when: 'New dispatcher · 18 min ago' },
  { icon: Navigation, tone: '#FF7A1A', title: 'V-014 accepted a detour', when: 'Harbor Avenue · 24 min ago' },
  { icon: CheckCircle2, tone: '#43D493', title: 'Westside Deliveries completed', when: '12 stops · 42 min ago' },
];

// Same illustrative-data caveat as the rest of this page.
export default function OverviewActivity() {
  return (
    <div className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-5">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <h2 className="font-display font-bold text-[15px] text-[#FFF9F1]">Activity</h2>
          <Info size={12} className="text-[#817970]" />
        </div>
        <button className="text-[11px] text-[#FF7A1A] font-semibold cursor-default">See all</button>
      </div>
      <p className="text-[11px] text-[#817970] mb-4">Recent updates from routes and teammates.</p>

      <div className="flex flex-col gap-3.5">
        {EVENTS.map(e => (
          <div key={e.title} className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${e.tone}22`, color: e.tone }}>
              <e.icon size={13} />
            </div>
            <div className="min-w-0">
              <div className="text-[12px] text-[#FFF9F1]">{e.title}</div>
              <div className="text-[10px] text-[#817970]">{e.when}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-[#2A2620] flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-[#173A2D] text-[#43D493] flex items-center justify-center flex-shrink-0">
          <Leaf size={13} />
        </div>
        <div>
          <div className="text-[12px] text-[#43D493] font-semibold">12.6 kg CO₂ avoided today</div>
          <div className="text-[10px] text-[#817970]">Estimated from shorter, smoother routes</div>
        </div>
      </div>
    </div>
  );
}
