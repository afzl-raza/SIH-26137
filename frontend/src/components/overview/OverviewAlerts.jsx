import React from 'react';
import { Info, AlertTriangle, Construction, CheckCircle2, GraduationCap } from 'lucide-react';

const ALERTS = [
  {
    icon: AlertTriangle, tone: 'warn',
    title: 'Slow traffic on Harbor Avenue', when: '2 min ago',
    detail: 'A crash is adding about 8 minutes for 3 vehicles.',
    action: 'Use Riverside detour →',
  },
  {
    icon: Construction, tone: 'caution',
    title: 'Road work begins at 2:00 PM', when: '12 min ago',
    detail: 'One lane will close near Central Depot.',
    action: 'Notify afternoon drivers →',
  },
  {
    icon: CheckCircle2, tone: 'good',
    title: 'Downtown traffic is easing', when: '18 min ago',
    detail: 'Routes through Market Street are moving normally.',
    action: 'No action needed →',
  },
];

const TONES = {
  warn: { bg: '#462122', fg: '#FF6868' },
  caution: { bg: '#46371D', fg: '#F5B942' },
  good: { bg: '#173A2D', fg: '#43D493' },
};

// Same illustrative-data caveat as OverviewMetrics: this prototype has no
// real incident feed. Static list matching the approved design's copy.
export default function OverviewAlerts() {
  return (
    <div className="flex flex-col gap-4">
      <div className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-5">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-1.5">
            <h2 className="font-display font-bold text-[15px] text-[#FFF9F1]">Traffic alerts</h2>
            <Info size={12} className="text-[#817970]" />
          </div>
          <button className="text-[11px] text-[#FF7A1A] font-semibold cursor-default">View all</button>
        </div>
        <p className="text-[11px] text-[#817970] mb-4">What changed and what to do next.</p>

        <div className="flex flex-col gap-4">
          {ALERTS.map(a => {
            const tone = TONES[a.tone];
            return (
              <div key={a.title} className="flex gap-2.5">
                <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5" style={{ backgroundColor: tone.bg, color: tone.fg }}>
                  <a.icon size={12} />
                </div>
                <div className="min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="text-[12.5px] font-semibold text-[#FFF9F1]">{a.title}</span>
                    <span className="text-[10px] text-[#817970] flex-shrink-0">{a.when}</span>
                  </div>
                  <p className="text-[11px] text-[#B9B0A5] mt-0.5">{a.detail}</p>
                  <span className="text-[11px] font-semibold cursor-default" style={{ color: tone.fg }}>{a.action}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-[#4A2916]/40 border border-[#5A3620] rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-2 text-[#F5B942]">
          <GraduationCap size={16} />
          <h3 className="font-display font-bold text-[14px] text-[#FFF9F1]">Need help?</h3>
        </div>
        <p className="text-[11px] text-[#B9B0A5] mb-3">
          Take a 3-minute tour of planning your first route.
        </p>
        <button className="bg-[#FF7A1A] hover:bg-[#E86D10] text-[#100F0D] font-display font-bold text-[12px] px-3.5 py-2 rounded-lg transition-colors">
          Start guided tour
        </button>
      </div>
    </div>
  );
}
