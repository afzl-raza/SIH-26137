import React from 'react';
import { CheckCircle2, AlertTriangle, ClipboardCheck, Truck, Route as RouteIcon, ShieldCheck, ShieldAlert } from 'lucide-react';
import SectionHeader from './SectionHeader';
import { stopsServed, affectedRoadCount } from './metrics';

export default function OperationalResult({ currentResult, scenario, networkState }) {
  const { served, total } = stopsServed(currentResult, scenario);
  const roadsAffected = affectedRoadCount(scenario);
  const allServed = served != null && total != null && served === total;
  const routeCount = currentResult.routes?.length ?? 0;

  const cards = [
    {
      icon: allServed ? CheckCircle2 : AlertTriangle,
      tone: allServed ? 'green' : 'amber',
      label: 'Stops Served',
      value: total != null ? `${served} / ${total}` : '—'
    },
    {
      icon: currentResult.is_feasible ? ShieldCheck : ShieldAlert,
      tone: currentResult.is_feasible ? 'green' : 'red',
      label: 'Route Plan',
      value: currentResult.is_feasible ? 'Feasible' : `${currentResult.constraint_violations || 0} issue(s)`
    },
    { icon: RouteIcon, tone: 'accent', label: 'Routes Created', value: String(routeCount) },
    { icon: Truck, tone: 'accent', label: 'Vehicles Used', value: String(routeCount) }
  ];

  if (roadsAffected > 0) {
    cards.push({
      icon: AlertTriangle,
      tone: 'amber',
      label: 'Roads Affected',
      value: `${roadsAffected} road${roadsAffected === 1 ? '' : 's'}`
    });
  }
  if (networkState === 'RE-OPTIMIZED') {
    cards.push({ icon: CheckCircle2, tone: 'green', label: 'Disruption Response', value: 'Plan updated' });
  }

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-3">
      <div className="space-y-1">
        <SectionHeader icon={ClipboardCheck} title="Is This Plan Ready to Use?" />
        <p className="text-xs text-gray-500">
          Checks that every stop is covered and no vehicle is overloaded or runs past its time limit.
        </p>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {cards.map((c, i) => <ResultCard key={i} {...c} />)}
      </div>
    </div>
  );
}

const TONES = {
  green: { bg: '#6B9A57', text: '#9FC589' },
  amber: { bg: '#E8A93A', text: '#E8C578' },
  red: { bg: '#C1443B', text: '#E8918A' },
  accent: { bg: '#C6602E', text: '#E8A578' }
};

function ResultCard({ icon: Icon, tone, label, value }) {
  const t = TONES[tone] || TONES.accent;
  return (
    <div className="bg-[#141210]/40 border border-[#332E29]/60 rounded-lg p-3 flex items-center gap-3">
      <div className="p-2 rounded-lg flex-shrink-0" style={{ backgroundColor: `${t.bg}1A`, color: t.text }}>
        <Icon size={18} />
      </div>
      <div className="flex flex-col min-w-0">
        <span className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">{label}</span>
        <span className="text-sm font-semibold text-gray-100 truncate">{value}</span>
      </div>
    </div>
  );
}
