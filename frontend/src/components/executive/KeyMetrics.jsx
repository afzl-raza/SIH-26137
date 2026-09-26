import React from 'react';
import { Clock, Navigation, Wallet, Cpu } from 'lucide-react';
import { useCountUp } from '../../lib/useCountUp';

// Real-data KPI grid - the numbers a viewer's eye should land on first,
// each with a one-line plain-language meaning. Colors match the icon-chip
// palette MetricCards.jsx already uses elsewhere in the app.
export default function KeyMetrics({ currentResult }) {
  return (
    <div className="space-y-2">
      <p className="text-xs text-gray-500 px-1">Totals for the whole fleet on the optimized route plan.</p>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Tile icon={Clock} color="#5F8A80" label="Travel Time" hint="Driving time, all vehicles" raw={currentResult.total_travel_time} decimals={1} suffix=" min" />
        <Tile icon={Navigation} color="#5D7A9E" label="Distance" hint="Kilometres driven, all vehicles" raw={currentResult.total_distance} decimals={1} suffix=" km" />
        <Tile icon={Wallet} color="#8C5A6E" label="Cost Score" hint="Time + distance + traffic; lower is better" raw={currentResult.total_cost} decimals={2} />
        <Tile icon={Cpu} color="#C99A3B" label="Planning Time" hint="How long the computer took" raw={(currentResult.runtime_ms ?? 0) / 1000} decimals={2} suffix=" s" />
      </div>
    </div>
  );
}

function Tile({ icon: Icon, color, label, hint, raw, decimals, suffix = '' }) {
  const animated = useCountUp(raw ?? 0, 800);
  return (
    <div className="clean-card p-3 sm:p-4 rounded-xl flex items-start gap-3">
      <div className="p-2 sm:p-2.5 rounded-lg flex-shrink-0" style={{ backgroundColor: `${color}1A`, color }}>
        <Icon size={20} />
      </div>
      <div className="flex flex-col min-w-0">
        <span className="text-gray-500 text-[10px] uppercase tracking-wider font-semibold">{label}</span>
        <span className="font-display text-base sm:text-lg font-bold text-white tabular-nums truncate">
          {animated.toFixed(decimals)}{suffix}
        </span>
        <span className="text-[10px] text-gray-500 leading-snug">{hint}</span>
      </div>
    </div>
  );
}
