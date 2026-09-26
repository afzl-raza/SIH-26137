import React from 'react';
import { CheckCircle2, AlertTriangle, ClipboardCheck } from 'lucide-react';
import SectionHeader from './SectionHeader';
import { stopsServed, affectedRoadCount } from './metrics';

export default function OperationalResult({ currentResult, scenario, networkState }) {
  const { served, total } = stopsServed(currentResult, scenario);
  const roadsAffected = affectedRoadCount(scenario);
  const allServed = served != null && total != null && served === total;
  const routeCount = currentResult.routes?.length ?? 0;

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-2">
      <SectionHeader icon={ClipboardCheck} title="Operational Result" />
      <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-1.5 text-[12px]">
        <Row ok={allServed} text={total != null ? `${served} / ${total} stops served` : 'Stops served: —'} />
        <Row
          ok={currentResult.is_feasible}
          text={currentResult.is_feasible ? 'Route plan is feasible' : `${currentResult.constraint_violations || 0} issue(s) with the plan`}
        />
        <Row ok text={`${routeCount} route${routeCount === 1 ? '' : 's'} created`} />
        <Row ok text={`${routeCount} vehicle${routeCount === 1 ? '' : 's'} used`} />
        {roadsAffected > 0 && <Row warn text={`${roadsAffected} road${roadsAffected === 1 ? '' : 's'} affected by disruption`} />}
        {networkState === 'RE-OPTIMIZED' && <Row ok text="Route plan updated after the disruption" />}
      </ul>
    </div>
  );
}

function Row({ ok, warn, text }) {
  const Icon = warn ? AlertTriangle : (ok ? CheckCircle2 : AlertTriangle);
  const color = warn ? 'text-[#E8A93A]' : (ok ? 'text-[#6B9A57]' : 'text-[#C1443B]');
  return (
    <li className={`flex items-center gap-2 ${color}`}>
      <Icon size={13} className="flex-shrink-0" />
      <span className="text-gray-300">{text}</span>
    </li>
  );
}
