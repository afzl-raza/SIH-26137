import React, { useState } from 'react';
import { Waypoints, Play, Zap, RotateCw, Activity } from 'lucide-react';
import { apiFetch } from '../api';
import Button from './ui/Button';

// Wires up the existing, self-contained Q-DFRO graph engine
// (`/api/qdfro-graph/*` in backend/main.py) - a real Sioux Falls (24-node,
// 76-directed-link) benchmark network with MSA traffic assignment and a
// live graph-based QPSO solver. This backend module already existed with
// no frontend surface at all; every value shown here comes straight from
// its responses - nothing is computed client-side or hardcoded.
export default function SiouxFallsPanel() {
  const [status, setStatus] = useState('idle'); // idle | ready | error
  const [error, setError] = useState(null);
  const [busyAction, setBusyAction] = useState(null); // 'init' | 'reoptimize' | 'incident'
  const [network, setNetwork] = useState(null); // { nodes, edges, vehicles }
  const [edgeOptions, setEdgeOptions] = useState([]);
  const [selectedEdge, setSelectedEdge] = useState('');
  const [routes, setRoutes] = useState(null); // { vehicleId: routeDict }
  const [previousRoutes, setPreviousRoutes] = useState(null);
  const [incidentResult, setIncidentResult] = useState(null);
  const [metrics, setMetrics] = useState(null);

  const loadEdgeOptions = async () => {
    const res = await apiFetch('/api/qdfro-graph/geojson');
    if (!res.ok) return;
    const geo = await res.json();
    const edges = (geo.features || [])
      .filter(f => f.geometry?.type === 'LineString' && f.properties?.road_class)
      .map(f => ({
        source: f.properties.source,
        target: f.properties.target,
        road_class: f.properties.road_class,
        saturation: f.properties.saturation
      }));
    setEdgeOptions(edges);
    if (edges.length > 0) setSelectedEdge(`${edges[0].source}|${edges[0].target}`);
  };

  const loadMetrics = async () => {
    const res = await apiFetch('/api/qdfro-graph/metrics');
    if (res.ok) setMetrics(await res.json());
  };

  const handleInitialize = async () => {
    setBusyAction('init');
    setError(null);
    try {
      const res = await apiFetch('/api/qdfro-graph/sioux-falls', { method: 'POST' });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to initialize Sioux Falls network');
      }
      const data = await res.json();
      setNetwork(data);
      setRoutes(null);
      setPreviousRoutes(null);
      setIncidentResult(null);
      setStatus('ready');
      await Promise.all([loadEdgeOptions(), loadMetrics()]);
    } catch (err) {
      setError(err.message);
      setStatus('error');
    } finally {
      setBusyAction(null);
    }
  };

  const handleReoptimize = async () => {
    setBusyAction('reoptimize');
    setError(null);
    try {
      const res = await apiFetch('/api/qdfro-graph/reoptimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || 'Re-optimization failed');
      }
      const data = await res.json();
      setPreviousRoutes(routes);
      setRoutes(data.routes);
      await loadMetrics();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyAction(null);
    }
  };

  const handleIncident = async () => {
    if (!selectedEdge) return;
    const [source, target] = selectedEdge.split('|');
    setBusyAction('incident');
    setError(null);
    try {
      const res = await apiFetch('/api/qdfro-graph/incident', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source, target, flag: 'blocked', severity: 1.0 })
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to trigger incident');
      }
      const data = await res.json();
      setIncidentResult(data);
      await loadMetrics();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyAction(null);
    }
  };

  if (status !== 'ready') {
    return (
      <div className="clean-panel rounded-xl border border-[#332E29] shadow-2xl p-4 space-y-3">
        <div className="flex items-center gap-2 text-gray-200 font-mono font-bold text-sm">
          <Waypoints size={16} className="text-[#5D7A9E]" />
          Sioux Falls Graph Engine (Q-DFRO)
        </div>
        <p className="text-[11px] text-gray-500 max-w-xl leading-relaxed">
          Independent benchmark network (24 nodes, 76 directed links - LeBlanc et al. 1975) with
          equilibrium MSA traffic assignment and a live graph-based QPSO solver. Separate from the
          scenario above - initializing it does not touch the current dashboard scenario or result.
        </p>
        <Button
          variant="secondary"
          size="sm"
          fullWidth={false}
          icon={busyAction === 'init' ? undefined : Play}
          loading={busyAction === 'init'}
          loadingText="Initializing (MSA assignment)..."
          onClick={handleInitialize}
        >
          Initialize Sioux Falls Network
        </Button>
        {error && <p className="text-[10px] text-[#E8918A]">{error}</p>}
      </div>
    );
  }

  const vehicleIds = network?.vehicles || [];

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] shadow-2xl p-4 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 text-gray-200 font-mono font-bold text-sm">
          <Waypoints size={16} className="text-[#5D7A9E]" />
          Sioux Falls Graph Engine (Q-DFRO)
        </div>
        <div className="text-[10px] text-gray-500 font-mono">
          {network.nodes} nodes · {network.edges} directed links · {vehicleIds.length} vehicles
        </div>
      </div>

      {error && <p className="text-[10px] text-[#E8918A]">{error}</p>}

      {/* Routes */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">Live QPSO Routes</span>
          <Button
            variant="secondary"
            size="sm"
            fullWidth={false}
            icon={busyAction === 'reoptimize' ? undefined : RotateCw}
            loading={busyAction === 'reoptimize'}
            loadingText="Solving..."
            onClick={handleReoptimize}
          >
            {routes ? 'Re-optimize' : 'Compute Routes'}
          </Button>
        </div>
        {routes ? (
          <div className="overflow-x-auto">
            <table className="w-full text-[11px] text-left font-mono">
              <thead className="text-gray-500 uppercase text-[9px]">
                <tr>
                  <th className="py-1 pr-2">Vehicle</th>
                  <th className="py-1 pr-2">Stops</th>
                  <th className="py-1 pr-2">Demand Served</th>
                  <th className="py-1 pr-2">Path</th>
                  <th className="py-1">Changed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#332E29]/60">
                {Object.entries(routes).map(([vid, r]) => {
                  const prev = previousRoutes?.[vid];
                  const changed = prev ? JSON.stringify(prev.nodes) !== JSON.stringify(r.nodes) : null;
                  return (
                    <tr key={vid} className="text-gray-300 tabular-nums align-top">
                      <td className="py-1 pr-2">{vid}</td>
                      <td className="py-1 pr-2">{r.nodes.length}</td>
                      <td className="py-1 pr-2">{r.demand_served}</td>
                      <td className="py-1 pr-2 text-gray-500 max-w-[220px] truncate" title={r.nodes.join(' → ')}>
                        {r.nodes.join(' → ')}
                      </td>
                      <td className={changed === null ? 'py-1 text-gray-600' : changed ? 'py-1 text-[#E8A93A]' : 'py-1 text-gray-600'}>
                        {changed === null ? '—' : changed ? 'Yes' : 'No'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-[10px] text-gray-600">Not yet computed for this session.</p>
        )}
      </div>

      {/* Incident */}
      <div className="space-y-1.5 pt-2 border-t border-[#332E29]">
        <span className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">Trigger Incident</span>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={selectedEdge}
            onChange={e => setSelectedEdge(e.target.value)}
            className="bg-[#1E1B18] border border-[#3A342E] text-gray-300 text-[11px] font-mono rounded px-2 py-1"
          >
            {edgeOptions.map(e => (
              <option key={`${e.source}|${e.target}`} value={`${e.source}|${e.target}`}>
                {e.source} → {e.target} ({e.road_class}, sat {e.saturation})
              </option>
            ))}
          </select>
          <Button
            variant="warning"
            size="sm"
            fullWidth={false}
            icon={busyAction === 'incident' ? undefined : Zap}
            loading={busyAction === 'incident'}
            loadingText="Applying..."
            disabled={!selectedEdge}
            onClick={handleIncident}
          >
            Block Selected Road
          </Button>
        </div>
        {incidentResult && (
          <div className="text-[10px] text-gray-400 font-mono space-y-0.5">
            {incidentResult.events.map((evt, i) => (
              <div key={i}>
                {evt.edge[0]} → {evt.edge[1]}: {evt.old_weight.toFixed(2)} → {evt.new_weight.toFixed(2)}
                {evt.is_blocked ? ' (blocked)' : ''}
              </div>
            ))}
            <div className="text-[#E8A93A]">
              Affected vehicles: {incidentResult.affected_vehicles.join(', ') || 'none'}
            </div>
          </div>
        )}
      </div>

      {/* Metrics */}
      {metrics && (
        <div className="space-y-1 pt-2 border-t border-[#332E29]">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-gray-500 font-semibold">
            <Activity size={12} className="text-[#6B9A57]" />
            Live Metrics
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono text-gray-300">
            <div>Sat. min <span className="text-gray-500">{metrics.link_saturation.min}</span></div>
            <div>Sat. max <span className="text-gray-500">{metrics.link_saturation.max}</span></div>
            <div>Conflicts <span className="text-gray-500">{metrics.spacetime.conflict_count}</span></div>
            <div>Penalty <span className="text-gray-500">{metrics.spacetime.penalty_score}</span></div>
          </div>
        </div>
      )}
    </div>
  );
}
