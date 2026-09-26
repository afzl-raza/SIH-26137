import React, { useState } from 'react';
import { Grid3x3, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { apiFetch } from '../api';
import { ALGORITHM_COLORS } from './BenchmarkPanel';

// Named parameter tuples for the EXISTING synthetic generator - not a
// separate topology engine. Per the project's evidence-integrity rule,
// these are always labeled as synthetic parameter presets and never
// implied to be real road data.
const ARCHETYPES = [
  {
    id: 'compact_core',
    label: 'Compact Core',
    description: 'Few nodes, tight radius, many jobs relative to nodes (dense).',
    params: { num_nodes: 12, num_jobs: 8, num_vehicles: 2 }
  },
  {
    id: 'sprawling_network',
    label: 'Sprawling Network',
    description: 'Many nodes, wide radius, fewer jobs relative to nodes (sparse).',
    params: { num_nodes: 60, num_jobs: 20, num_vehicles: 5 }
  },
  {
    id: 'balanced_grid',
    label: 'Balanced Grid',
    description: "The generator's default shape - kept as the baseline/control.",
    params: { num_nodes: 30, num_jobs: 15, num_vehicles: 3 }
  }
];

const ALGO_COLUMNS = [
  { key: 'greedy', label: 'Greedy' },
  { key: 'pso', label: 'PSO' },
  { key: 'ga', label: 'GA' },
  { key: 'qpso', label: 'QPSO' },
  { key: 'qpso_ls', label: 'QPSO+LS' },
  { key: 'exact', label: 'Exact' }
];

function algoColor(id) {
  return ALGORITHM_COLORS[id]?.hex || '#9CA3AF';
}

export default function ArchetypeBenchmarkPanel({ config }) {
  const [selected, setSelected] = useState(ARCHETYPES.map(a => a.id));
  const [running, setRunning] = useState(false);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);

  const toggleArchetype = (id) => {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  // Sequential, real calls to the same endpoints the main dashboard uses -
  // no new backend surface, no client-side objective math. Each archetype's
  // scenario is generated and benchmarked independently; nothing here
  // touches the main dashboard's active scenario/result state.
  const runMatrix = async () => {
    const chosen = ARCHETYPES.filter(a => selected.includes(a.id));
    if (chosen.length === 0) return;
    setRunning(true);
    setError(null);
    const nextRows = [];
    try {
      for (const archetype of chosen) {
        const genRes = await apiFetch('/api/problem/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source: 'synthetic',
            seed: config.seed,
            ...archetype.params
          }),
          timeoutMs: 30000
        });
        if (!genRes.ok) {
          const detail = await genRes.json().catch(() => null);
          throw new Error(detail?.detail || `Failed to generate "${archetype.label}"`);
        }
        const genData = await genRes.json();

        const bmRes = await apiFetch('/api/benchmark', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scenario_id: genData.scenario_id, config }),
          timeoutMs: 120000
        });
        if (!bmRes.ok) {
          const detail = await bmRes.json().catch(() => null);
          throw new Error(detail?.detail || `Benchmark failed for "${archetype.label}"`);
        }
        const bmData = await bmRes.json();

        nextRows.push({
          id: archetype.id,
          label: archetype.label,
          description: archetype.description,
          nodeCount: genData.node_count,
          jobCount: genData.job_count,
          vehicleCount: genData.vehicle_count,
          results: bmData.results
        });
        // Progressive render: each archetype's row appears as soon as its
        // own benchmark completes, rather than waiting for the whole matrix.
        setRows([...nextRows]);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] shadow-2xl p-4 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 text-gray-200 font-mono font-bold text-sm">
          <Grid3x3 size={16} className="text-[#C6602E]" />
          Archetype Benchmark Matrix
        </div>
        <button
          onClick={runMatrix}
          disabled={running || selected.length === 0}
          className="px-3 py-1.5 bg-[#C6602E] hover:bg-[#B5542A] text-white rounded text-[11px] font-mono font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5"
        >
          {running && <Loader2 size={12} className="animate-spin" />}
          {running ? 'Running…' : 'Run Matrix'}
        </button>
      </div>

      <p className="text-[10px] text-gray-500 leading-snug">
        Each archetype below is a synthetic parameter preset for the same generator
        the rest of this demo uses - not a distinct topology engine, and not real
        road data. Selecting archetypes and running the matrix issues real
        generate + benchmark calls per archetype; nothing here is precomputed.
      </p>

      <div className="flex flex-wrap gap-2">
        {ARCHETYPES.map(a => (
          <button
            key={a.id}
            onClick={() => toggleArchetype(a.id)}
            disabled={running}
            aria-pressed={selected.includes(a.id)}
            title={a.description}
            className={`px-2.5 py-1 rounded border text-[11px] font-mono transition-colors disabled:opacity-40 ${
              selected.includes(a.id)
                ? 'bg-[#2A2018] border-[#C6602E] text-[#E8A93A]'
                : 'bg-[#26221D] border-[#3A342E] text-gray-400 hover:text-gray-200'
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>

      {error && (
        <p className="text-[11px] text-[#E8918A] bg-[#3A1C18]/50 border border-[#5A2A22] rounded px-2 py-1">
          {error}
        </p>
      )}

      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px] font-mono border-collapse">
            <thead>
              <tr className="text-gray-500 border-b border-[#332E29]">
                <th className="text-left py-1.5 pr-3">Archetype</th>
                {ALGO_COLUMNS.map(col => (
                  <th key={col.key} className="text-right py-1.5 px-2" style={{ color: algoColor(col.key) }}>
                    {col.label}
                  </th>
                ))}
                <th className="text-right py-1.5 pl-2">Feasible</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const presentCols = ALGO_COLUMNS.filter(c => row.results[c.key]);
                const feasibleCount = presentCols.filter(c => row.results[c.key].is_feasible).length;
                return (
                  <tr key={row.id} className="border-b border-[#26221D]">
                    <td className="py-1.5 pr-3 text-gray-300">
                      <div className="font-semibold">{row.label}</div>
                      <div className="text-[9px] text-gray-600">
                        {row.nodeCount} nodes · {row.jobCount} jobs · {row.vehicleCount} vehicles
                      </div>
                    </td>
                    {ALGO_COLUMNS.map(col => {
                      const res = row.results[col.key];
                      if (!res) {
                        return <td key={col.key} className="text-right py-1.5 px-2 text-gray-700">—</td>;
                      }
                      return (
                        <td key={col.key} className="text-right py-1.5 px-2">
                          <span className="text-gray-200">{res.total_cost.toFixed(1)}</span>{' '}
                          {res.is_feasible
                            ? <CheckCircle2 size={11} className="inline text-[#6B9A57] mb-0.5" />
                            : <XCircle size={11} className="inline text-[#C1443B] mb-0.5" />}
                        </td>
                      );
                    })}
                    <td className="text-right py-1.5 pl-2 text-gray-400">
                      {feasibleCount}/{presentCols.length}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
