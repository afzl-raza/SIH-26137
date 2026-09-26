import React, { useMemo, useState } from 'react';
import { Route as RouteIcon } from 'lucide-react';
import SegmentedControl from '../ui/SegmentedControl';
import SectionHeader from './SectionHeader';

// A stylized, tilted route-flow diagram - not a second copy of the Leaflet
// operational map (that already lives in the Engineering Control Room and
// in Route Details below). Same real node positions and the same real
// node_path/job_ids the optimizer actually returned; only the presentation
// is different: a dark isometric "board" instead of map tiles, built with
// plain SVG + a CSS 3D tilt, no charting/3D library added.
const WIDTH = 640;
const HEIGHT = 340;
const PAD = 34;

function makeProjector(nodes) {
  if (!nodes.length) return () => [WIDTH / 2, HEIGHT / 2];
  const lats = nodes.map(n => n.lat);
  const lngs = nodes.map(n => n.lng);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
  const latSpan = maxLat - minLat || 1;
  const lngSpan = maxLng - minLng || 1;
  const innerW = WIDTH - PAD * 2;
  const innerH = HEIGHT - PAD * 2;
  return (lat, lng) => [
    PAD + ((lng - minLng) / lngSpan) * innerW,
    // Flip Y: latitude increases upward, SVG y increases downward.
    PAD + (1 - (lat - minLat) / latSpan) * innerH
  ];
}

function RouteLayer({ nodes, nodeById, jobs, depotNode, result, vehicles, project, active }) {
  const routes = result?.routes || [];

  const jobIdToNodeId = useMemo(() => new Map(jobs.map(j => [j.id, j.node_id])), [jobs]);
  const servedNodeIds = useMemo(
    () => new Set(routes.flatMap(r => (r.job_ids || []).map(jid => jobIdToNodeId.get(jid))).filter(Boolean)),
    [routes, jobIdToNodeId]
  );

  const projectedRoutes = useMemo(() => routes.map(r => {
    const pts = (r.node_path || []).map(id => nodeById.get(id)).filter(Boolean).map(n => project(n.lat, n.lng));
    const color = vehicles.find(v => v.id === r.vehicle_id)?.color || '#C6602E';
    const d = pts.length > 1 ? `M ${pts.map(p => p.join(' ')).join(' L ')}` : '';
    return { vehicleId: r.vehicle_id, color, d };
  }), [routes, nodeById, project, vehicles]);

  const stopNodes = nodes.filter(n => !n.is_depot && jobIdToNodeId && [...jobIdToNodeId.values()].includes(n.id));

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className={`absolute inset-0 w-full h-full transition-opacity duration-500 ease-out ${active ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
    >
      {/* Before any route exists, faint dashed spokes from the depot show
          the delivery points waiting to be served - real positions, no
          route computed yet, so no colored path is drawn. */}
      {routes.length === 0 && depotNode && stopNodes.map(n => {
        const [dx, dy] = project(depotNode.lat, depotNode.lng);
        const [x, y] = project(n.lat, n.lng);
        return (
          <line key={`hint-${n.id}`} x1={dx} y1={dy} x2={x} y2={y}
            stroke="#3A342E" strokeWidth="1" strokeDasharray="2,5" opacity="0.6" />
        );
      })}

      {projectedRoutes.map(r => r.d && (
        <path
          key={`route-${r.vehicleId}`}
          d={r.d}
          fill="none"
          stroke={r.color}
          strokeWidth="3.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ filter: `drop-shadow(0 2px 4px ${r.color}99)` }}
        />
      ))}

      {stopNodes.map(n => {
        const [x, y] = project(n.lat, n.lng);
        const served = servedNodeIds.has(n.id);
        return (
          <g key={`stop-${n.id}`}>
            <ellipse cx={x} cy={y + 3} rx="5" ry="2" fill="#000" opacity="0.35" />
            <circle
              cx={x} cy={y} r="4.5"
              fill={served ? '#1E1B18' : '#0D0C0B'}
              stroke={served ? '#5D7A9E' : '#4A423A'}
              strokeWidth="1.6"
            />
          </g>
        );
      })}

      {depotNode && (() => {
        const [x, y] = project(depotNode.lat, depotNode.lng);
        return (
          <g>
            <ellipse cx={x} cy={y + 6} rx="11" ry="4" fill="#000" opacity="0.45" />
            <circle cx={x} cy={y} r="9" fill="#1E1B18" stroke="#C1443B" strokeWidth="2" />
            <circle cx={x} cy={y} r="3" fill="#C1443B" />
          </g>
        );
      })()}
    </svg>
  );
}

export default function NetworkComparison({ scenario, beforeResult, afterResult }) {
  const [mode, setMode] = useState('after');
  const nodes = scenario?.nodes || [];
  const jobs = scenario?.jobs || [];
  const vehicles = scenario?.vehicles || [];
  const nodeById = useMemo(() => new Map(nodes.map(n => [n.id, n])), [nodes]);
  const depotNode = nodes.find(n => n.is_depot) || nodeById.get(scenario?.depot_node_id);
  const project = useMemo(() => makeProjector(nodes), [nodes]);

  const shown = mode === 'before' ? beforeResult : afterResult;
  const routeCount = shown?.routes?.length ?? 0;
  const stopCount = shown?.routes
    ? new Set(shown.routes.flatMap(r => r.job_ids || [])).size
    : 0;

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <SectionHeader icon={RouteIcon} title="Before vs Optimized Network" />
        <div className="w-64">
          <SegmentedControl
            options={[
              { id: 'before', label: 'Before Optimization' },
              { id: 'after', label: 'Optimized Result', activeColor: '#C6602E' }
            ]}
            value={mode}
            onChange={setMode}
          />
        </div>
      </div>

      <div style={{ perspective: '1400px' }}>
        <div
          className="relative w-full rounded-xl border border-[#332E29] overflow-hidden bg-gradient-to-b from-[#171513] to-[#0D0C0B]"
          style={{
            height: HEIGHT,
            transform: 'rotateX(20deg) scale(0.98)',
            transformOrigin: 'center top',
            boxShadow: '0 34px 60px -24px rgba(0,0,0,0.65), 0 0 0 1px rgba(198,96,46,0.05)'
          }}
        >
          <RouteLayer
            nodes={nodes} nodeById={nodeById} jobs={jobs} depotNode={depotNode}
            result={beforeResult} vehicles={vehicles} project={project}
            active={mode === 'before'}
          />
          <RouteLayer
            nodes={nodes} nodeById={nodeById} jobs={jobs} depotNode={depotNode}
            result={afterResult} vehicles={vehicles} project={project}
            active={mode === 'after'}
          />

          <div className="absolute top-3 left-3 text-[9px] font-mono uppercase tracking-wider text-gray-400 bg-[#0D0C0B]/70 px-2 py-1 rounded">
            {mode === 'before' ? 'Before Optimization' : 'Optimized Result'}
          </div>
          <div className="absolute bottom-3 right-3 text-[10px] font-mono text-gray-300 bg-[#0D0C0B]/70 px-2 py-1 rounded">
            {routeCount} route{routeCount === 1 ? '' : 's'} · {stopCount} stop{stopCount === 1 ? '' : 's'}
          </div>
        </div>
      </div>
    </div>
  );
}
