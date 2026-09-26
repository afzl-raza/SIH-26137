import React, { useMemo, useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import { apiFetch } from '../api';
import { CONGESTION_ORDER, CONGESTION_STYLES, INCIDENT_STYLE, congestionStyle, congestionLabel } from '../lib/traffic';
import VehicleLoader from './ui/VehicleLoader';
import SegmentedControl from './ui/SegmentedControl';
import Button from './ui/Button';

// Asks the backend for the road shape of an already-computed set of routes.
//
// This does NOT route. The optimizer's `node_path` is already the complete
// node-by-node road path; the backend simply looks up the OpenStreetMap
// geometry of each hop (see backend/route_geometry.py) using the same
// parallel-edge rule the router used. No path-finding of any kind happens in
// React.
//
// Only OpenStreetMap scenarios ask: a synthetic network has no road geometry,
// so it keeps the straight-line rendering it has always had and skips the
// round-trip entirely.
function useBackendRouteGeometry(scenarioId, result, enabled) {
  const [geometry, setGeometry] = useState(null);

  useEffect(() => {
    if (!enabled || !scenarioId || !result?.routes?.length) {
      setGeometry(null);
      return;
    }
    let cancelled = false;
    apiFetch('/api/routes/geometry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId, routes: result.routes })
    })
      .then(res => (res.ok ? res.json() : null))
      .then(data => {
        if (cancelled || !data?.routes) return;
        const byVehicle = new Map();
        data.routes.forEach(r => byVehicle.set(r.vehicle_id, r));
        setGeometry({ byVehicle, source: data.geometry_source });
      })
      // A failed lookup is not fatal: the caller falls back to the
      // junction-to-junction line, which is real data too, just coarser.
      .catch(() => { if (!cancelled) setGeometry(null); });
    return () => { cancelled = true; };
  }, [scenarioId, result, enabled]);

  return geometry;
}

// Animates a 0->1 progress value whenever `resultObj` becomes a *new*
// object (i.e. a fresh optimize/re-optimize result arrived) - used to fade
// the previous route out and the new route in. Both routes being faded are
// real, already-computed coordinate arrays; this only transitions opacity,
// it never invents an intermediate path.
function useRouteTransition(resultObj, duration = 800) {
  const [progress, setProgress] = useState(1);
  const prevRef = useRef(resultObj);

  useEffect(() => {
    if (resultObj === prevRef.current) return;
    prevRef.current = resultObj;
    if (!resultObj) return;
    setProgress(0);
    const start = performance.now();
    let raf;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      setProgress(t);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [resultObj, duration]);

  return progress;
}

// Custom Marker HTML Generators - hand-drawn inline SVG glyphs instead of
// emoji (emoji renders inconsistently across OSes and is a strong
// "default/AI-generated" tell). Colors follow the asphalt/traffic palette.
const createDepotMarkerIcon = () => L.divIcon({
  html: `<div style="background:#1E1B18; border:2px solid #C1443B; border-radius:6px; padding:2px 6px; color:#E8918A; font-family:JetBrains Mono, monospace; font-size:10px; font-weight:bold; box-shadow:0 4px 12px rgba(193,68,59,0.35); display:flex; align-items:center; gap:4px;">
          <svg width="9" height="9" viewBox="0 0 10 10"><rect x="1" y="1" width="8" height="8" rx="2" fill="none" stroke="#C1443B" stroke-width="1.5"/></svg>
          <span>DEPOT</span>
         </div>`,
  className: 'custom-leaflet-depot',
  iconSize: [60, 24],
  iconAnchor: [30, 12]
});

const createJobMarkerIcon = (jobId) => L.divIcon({
  html: `<div style="background:#1E1B18; border:1.5px solid #5D7A9E; border-radius:12px; padding:1px 6px; color:#9AB3CC; font-family:JetBrains Mono, monospace; font-size:10px; font-weight:600; box-shadow:0 2px 8px rgba(0,0,0,0.5); display:flex; align-items:center; gap:3px;">
          <svg width="7" height="7" viewBox="0 0 8 8"><circle cx="4" cy="4" r="3.2" fill="#5D7A9E"/></svg>
          <span>D${jobId < 10 ? '0' + jobId : jobId}</span>
         </div>`,
  className: 'custom-leaflet-job',
  iconSize: [48, 20],
  iconAnchor: [24, 10]
});

// Manual placement is a draft until confirmed, so its markers are visually
// distinct (dashed border, different accent) from the committed depot/job
// markers above - never implying the pick is already applied.
const createDraftDepotMarkerIcon = () => L.divIcon({
  html: `<div style="background:#1E1B18; border:2px dashed #C6602E; border-radius:6px; padding:2px 6px; color:#E8A93A; font-family:JetBrains Mono, monospace; font-size:10px; font-weight:bold; box-shadow:0 4px 12px rgba(198,96,46,0.35); display:flex; align-items:center; gap:4px;">
          <svg width="9" height="9" viewBox="0 0 10 10"><rect x="1" y="1" width="8" height="8" rx="2" fill="none" stroke="#C6602E" stroke-width="1.5"/></svg>
          <span>DEPOT (draft)</span>
         </div>`,
  className: 'custom-leaflet-draft-depot',
  iconSize: [90, 24],
  iconAnchor: [45, 12]
});

const createDraftStopMarkerIcon = (index) => L.divIcon({
  html: `<div style="background:#1E1B18; border:1.5px dashed #6B9A57; border-radius:12px; padding:1px 6px; color:#9ABF87; font-family:JetBrains Mono, monospace; font-size:10px; font-weight:600; box-shadow:0 2px 8px rgba(0,0,0,0.5); display:flex; align-items:center; gap:3px;">
          <svg width="7" height="7" viewBox="0 0 8 8"><circle cx="4" cy="4" r="3.2" fill="#6B9A57"/></svg>
          <span>S${index < 10 ? '0' + index : index}</span>
         </div>`,
  className: 'custom-leaflet-draft-stop',
  iconSize: [48, 20],
  iconAnchor: [24, 10]
});

const createVehicleMarkerIcon = (vehicleId, color, isSelected) => L.divIcon({
  html: `<div style="background:#1E1B18; border:${isSelected ? '3px' : '2px'} solid ${color}; border-radius:12px; padding:2px 7px; color:#FFFFFF; font-family:JetBrains Mono, monospace; font-size:10px; font-weight:bold; box-shadow:0 4px 14px ${color}66; display:flex; align-items:center; gap:4px; transform:scale(${isSelected ? '1.15' : '1.0'});">
          <svg width="13" height="9" viewBox="0 0 16 10"><rect x="0.5" y="1.5" width="10" height="6.5" rx="1" fill="${color}"/><rect x="10.5" y="3.5" width="4.5" height="4.5" rx="0.8" fill="${color}"/><circle cx="4" cy="9" r="1.3" fill="#1E1B18" stroke="${color}" stroke-width="1"/><circle cx="12.5" cy="9" r="1.3" fill="#1E1B18" stroke="${color}" stroke-width="1"/></svg>
          <span>V${vehicleId < 10 ? '0' + vehicleId : vehicleId}</span>
         </div>`,
  className: 'custom-leaflet-vehicle',
  iconSize: [48, 24],
  iconAnchor: [24, 12]
});

export default function NetworkMap({
  scenario,
  scenarioId,
  loading,
  currentResult,
  previousResult,
  selectedIncidentEdge,
  selectedVehicleId,
  onSelectVehicle,
  weights,
  onDisruptEdge,
  disruptDisabled,
  previewResult,
  previewedAlgorithm,
  placementMode = false,
  draftDepotId = null,
  draftStopIds = [],
  onPlaceNode,
  // Stripped-down read-only mode for side-by-side comparisons: no GIS/Graph
  // toggle, no vehicle filter bar, no legend, and no scroll-wheel zoom (two
  // maps next to each other would otherwise hijack page scrolling).
  compact = false
}) {
  const [vehicleFilter, setVehicleFilter] = useState('all');
  const [mapView, setMapView] = useState('gis'); // 'gis' | 'graph' - same real nodes/edges, just a render toggle
  const [isLegendOpen, setIsLegendOpen] = useState(false);
  const routeTransition = useRouteTransition(currentResult);
  // 'both' (default) keeps today's automatic fade; the other three let the
  // operator pin the comparison instead of relying on catching the 800ms
  // transition. Same real previous/active route coordinates either way -
  // this only changes which are visible and at what opacity.
  const [beforeAfterMode, setBeforeAfterMode] = useState('both'); // 'both' | 'before' | 'after' | 'overlay'

  // ALL hooks must be called unconditionally before any early return
  const nodes = scenario?.nodes || [];
  const edges = scenario?.edges || [];
  const jobs = scenario?.jobs || [];
  const vehicles = scenario?.vehicles || [];

  const center = useMemo(() => {
    if (nodes.length === 0) return [12.9716, 77.5946];
    const lats = nodes.map(n => n.lat);
    const lngs = nodes.map(n => n.lng);
    return [
      lats.reduce((a, b) => a + b, 0) / lats.length,
      lngs.reduce((a, b) => a + b, 0) / lngs.length
    ];
  }, [nodes]);

  const nodeMap = useMemo(() => {
    const map = new Map();
    nodes.forEach(n => map.set(n.id, n));
    return map;
  }, [nodes]);

  const jobNodeIds = useMemo(() => new Set(jobs.map(j => j.node_id)), [jobs]);

  const jobMap = useMemo(() => {
    const map = new Map();
    jobs.forEach(j => map.set(j.node_id, j));
    return map;
  }, [jobs]);

  // True when this network's roads carry real OpenStreetMap geometry. Drives
  // the two things Phase 6 makes conditional: drawing road shapes instead of
  // straight lines, and asking the backend for route geometry. Synthetic
  // scenarios answer false and keep their original rendering unchanged.
  const isOsmNetwork = scenario?.data_source === 'openstreetmap';

  const edgeLines = useMemo(() => {
    const drawn = new Set();
    const list = [];

    edges.forEach(e => {
      const key = [Math.min(e.source, e.destination), Math.max(e.source, e.destination)].join('-');
      if (drawn.has(key)) return;
      drawn.add(key);

      const n1 = nodeMap.get(e.source);
      const n2 = nodeMap.get(e.destination);
      if (!n1 || !n2) return;

      const isSelectedIncident = selectedIncidentEdge && (
        (selectedIncidentEdge.source === e.source && selectedIncidentEdge.destination === e.destination) ||
        (selectedIncidentEdge.source === e.destination && selectedIncidentEdge.destination === e.source)
      );
      // The backend flags the incident axis itself, so a disruption applied
      // any other way (a replayed scenario, a second operator) still shows.
      const isIncident = Boolean(isSelectedIncident || e.has_incident);

      // Real OSM way geometry when the edge has it - including the shape
      // points that were collapsed out of the routing graph - otherwise the
      // junction-to-junction line a synthetic network has always drawn.
      const hasRealGeometry = Array.isArray(e.geometry) && e.geometry.length >= 2;
      const positions = hasRealGeometry
        ? e.geometry
        : [[n1.lat, n1.lng], [n2.lat, n2.lng]];

      // Colour/width come entirely from the band the backend assigned.
      const style = isIncident ? INCIDENT_STYLE : congestionStyle(e);

      list.push({
        id: key,
        source: e.source,
        destination: e.destination,
        positions,
        geometrySource: hasRealGeometry ? 'openstreetmap' : 'straight-line',
        color: style.color,
        weight: style.weight,
        opacity: style.opacity,
        isIncident,
        congestionLabel: congestionLabel(e),
        congestionLevel: e.congestion_level || 'free_flow',
        trafficFactor: e.traffic_factor,
        trafficMultiplier: e.traffic_multiplier,
        weatherMultiplier: e.weather_multiplier,
        incidentMultiplier: e.incident_multiplier,
        roadName: e.road_name,
        highway: e.highway,
        osmWayId: e.osm_way_id,
        speedKph: e.speed_kph,
        speedSource: e.speed_source,
        baseTime: e.base_travel_time,
        currentTime: e.current_travel_time,
        distance: e.distance
      });
    });

    return list;
  }, [edges, nodeMap, selectedIncidentEdge]);

  // Derived, not new state: reuses edgeLines' own dedup (one entry per
  // undirected pair) so this list can never disagree with what the map
  // itself is drawing as an incident.
  const closedEdges = useMemo(
    () => edgeLines.filter(e => e.isIncident),
    [edgeLines]
  );

  const displayedResult = previewResult || currentResult;

  const activeRouteGeometry = useBackendRouteGeometry(scenarioId, displayedResult, isOsmNetwork);
  const previousRouteGeometry = useBackendRouteGeometry(scenarioId, previousResult, isOsmNetwork);

  // The node-path fallback: the straight line between each pair of nodes the
  // optimizer's path visits. Still the optimizer's own route - only its shape
  // is approximated - and it is what a synthetic network legitimately looks
  // like, since its roads are straight lines.
  const nodePathCoords = useMemo(() => (route) =>
    route.node_path
      .map(nid => {
        const node = nodeMap.get(nid);
        return node ? [node.lat, node.lng] : null;
      })
      .filter(Boolean),
  [nodeMap]);

  const activeRouteLines = useMemo(() => {
    if (!displayedResult || !displayedResult.routes) return [];
    const vColorMap = new Map(vehicles.map(v => [v.id, v.color]));

    return displayedResult.routes.map(r => {
      // Prefer the backend's resolved road geometry; fall back to the node
      // path while the lookup is in flight, when it fails, or for a synthetic
      // network that has no geometry to resolve.
      const resolved = activeRouteGeometry?.byVehicle?.get(r.vehicle_id);
      const usingRoadGeometry = Boolean(resolved?.polyline?.length);
      const coords = usingRoadGeometry ? resolved.polyline : nodePathCoords(r);

      const isSelected = selectedVehicleId === r.vehicle_id || vehicleFilter === r.vehicle_id;
      const isFilteredOut = vehicleFilter !== 'all' && vehicleFilter !== r.vehicle_id;

      return {
        vehicleId: r.vehicle_id,
        color: vColorMap.get(r.vehicle_id) || '#C6602E',
        coords,
        geometrySource: usingRoadGeometry ? resolved.geometry_source : 'straight-line',
        jobsCount: r.job_ids.length,
        dist: r.route_distance,
        time: r.route_travel_time,
        isSelected, isFilteredOut,
        routeObj: r
      };
    });
  }, [displayedResult, vehicles, nodePathCoords, activeRouteGeometry, selectedVehicleId, vehicleFilter]);

  // Per-vehicle-color glow rule, applied via className (not a duplicated
  // Polyline) - avoids the zoom/pan micro-stutter a second SVG path per
  // route would add.
  const routeGlowCss = useMemo(() => {
    return activeRouteLines
      .map(ar => `.route-glow-v${ar.vehicleId} { filter: drop-shadow(0 0 4px ${ar.color}); }`)
      .join('\n');
  }, [activeRouteLines]);

  const vehicleMarkers = useMemo(() => {
    if (activeRouteLines.length === 0) return [];

    const numV = activeRouteLines.length;
    const depotNode = nodes.find(n => n.is_depot) || nodes[0];
    if (!depotNode) return [];

    return activeRouteLines.map((ar, idx) => {
      let position = [depotNode.lat, depotNode.lng];

      if (ar.coords.length > 2) {
        const firstStop = ar.coords[1];
        const secondStop = ar.coords[Math.min(2, ar.coords.length - 1)];
        position = [
          (firstStop[0] + secondStop[0]) / 2,
          (firstStop[1] + secondStop[1]) / 2
        ];
      } else if (ar.coords.length === 2) {
        position = ar.coords[1];
      } else {
        const angle = (2 * Math.PI * idx) / numV;
        position = [
          depotNode.lat + 0.003 * Math.cos(angle),
          depotNode.lng + 0.003 * Math.sin(angle)
        ];
      }

      const vehicleObj = vehicles.find(v => v.id === ar.vehicleId);

      return {
        vehicleId: ar.vehicleId,
        color: ar.color,
        position,
        jobsCount: ar.jobsCount,
        dist: ar.dist,
        time: ar.time,
        isSelected: ar.isSelected,
        vehicleObj,
        routeObj: ar.routeObj
      };
    });
  }, [activeRouteLines, nodes, vehicles]);

  const previousRouteLines = useMemo(() => {
    if (!previousResult || !previousResult.routes) return [];

    return previousResult.routes.map(r => {
      const resolved = previousRouteGeometry?.byVehicle?.get(r.vehicle_id);
      const coords = resolved?.polyline?.length ? resolved.polyline : nodePathCoords(r);
      return { vehicleId: r.vehicle_id, coords };
    });
  }, [previousResult, nodePathCoords, previousRouteGeometry]);

  // NOW the early return, after all hooks
  if (nodes.length === 0) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-[#171513] text-gray-400 font-mono text-xs rounded-xl border border-[#332E29]">
        {loading ? (
          <VehicleLoader label="Loading Network" sublabel="Building the road network for this scenario..." />
        ) : (
          <span>Generate a scenario to begin fleet route optimization.</span>
        )}
      </div>
    );
  }

  return (
    // `isolate` gives the map its own stacking context, so Leaflet's
    // internal z-indexes (panes 400+, controls 1000) can't escape it and
    // paint over the sticky header or other page chrome while scrolling.
    <div className="w-full h-full relative rounded-xl overflow-hidden border border-[#332E29] shadow-2xl flex flex-col isolate">
      {routeGlowCss && <style>{routeGlowCss}</style>}
      {previewResult && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[1001] bg-[#3A2318] border border-[#5A3A22] text-[#E8A578] px-3 py-1 rounded-full text-[11px] font-mono font-semibold shadow-xl">
          PREVIEWING: {(previewedAlgorithm || '').toUpperCase()} routes (benchmark result, not applied)
        </div>
      )}

      {/* GIS <-> Graph View toggle - same real nodes/edges either way */}
      {!compact && (
        <div className="absolute top-3 right-3 z-[1000] clean-panel p-1 rounded-lg border border-[#332E29] shadow-xl pointer-events-auto font-mono w-32">
          <SegmentedControl
            options={[
              { id: 'gis', label: 'GIS View', title: 'Geographic road-network view.' },
              { id: 'graph', label: 'Graph View', title: 'Network topology view.' }
            ]}
            value={mapView}
            onChange={setMapView}
          />
        </div>
      )}

      {/* Before/After comparison toggle - only meaningful once there is a
          previous route to compare the active one against. Same underlying
          coordinates as the automatic post-re-optimize fade; this just lets
          the operator pin the comparison instead of relying on catching an
          800ms transition. */}
      {previousResult && currentResult && (
        <div className="absolute top-14 right-3 z-[1000] clean-panel px-2 py-1.5 rounded-lg text-xs border border-[#332E29] shadow-xl pointer-events-auto font-mono space-y-1.5">
          <div className="flex items-center gap-1">
            {[
              { id: 'both', label: 'Show Both' },
              { id: 'before', label: 'Before Only' },
              { id: 'after', label: 'After Only' },
              { id: 'overlay', label: 'Overlay' }
            ].map(opt => (
              <button
                key={opt.id}
                onClick={() => setBeforeAfterMode(opt.id)}
                aria-pressed={beforeAfterMode === opt.id}
                className={`px-1.5 py-0.5 rounded text-[9px] font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-[#C6602E] ${
                  beforeAfterMode === opt.id ? 'bg-[#C6602E] text-white' : 'bg-[#26221D] text-gray-400 hover:text-gray-200'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {/* Which visual style means which - not just the existing
              dashed-vs-solid line difference. */}
          <div className="flex items-center gap-3 text-[9px]">
            <span className="flex items-center gap-1 text-gray-400">
              <span className="inline-block w-3 h-0 border-t-2 border-dashed" style={{ borderColor: '#6B6259' }} />
              BEFORE
            </span>
            <span className="flex items-center gap-1 text-[#C6602E] font-semibold">
              <span className="inline-block w-3 h-0.5 bg-[#C6602E]" />
              AFTER
            </span>
          </div>
        </div>
      )}

      {/* Top Filter Bar for Vehicles */}
      {!compact && vehicles.length > 0 && (
        <div className="absolute top-14 sm:top-3 left-3 z-[1000] clean-panel px-3 py-1.5 rounded-lg text-xs flex items-center space-x-2 border border-[#332E29] shadow-xl pointer-events-auto font-mono max-w-[calc(100%-1.5rem)] sm:max-w-md overflow-x-auto">
          <span className="text-gray-400 text-[10px] uppercase font-bold tracking-wider flex-shrink-0">ROUTES:</span>
          <button
            onClick={() => setVehicleFilter('all')}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors flex-shrink-0 focus-visible:ring-2 focus-visible:ring-[#C6602E] ${
              vehicleFilter === 'all' ? 'bg-[#C6602E] text-white' : 'bg-[#26221D] text-gray-400 hover:text-gray-200'
            }`}
          >
            ALL ({vehicles.length})
          </button>
          {vehicles.map(v => (
            <button
              key={v.id}
              onClick={() => {
                setVehicleFilter(v.id);
                const rObj = currentResult?.routes?.find(r => r.vehicle_id === v.id);
                if (onSelectVehicle) onSelectVehicle(v, rObj);
              }}
              className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors flex items-center space-x-1 flex-shrink-0 focus-visible:ring-2 focus-visible:ring-[#C6602E] ${
                vehicleFilter === v.id || selectedVehicleId === v.id
                  ? 'text-white shadow-md'
                  : 'bg-[#26221D] text-gray-400 hover:text-gray-200'
              }`}
              style={{
                backgroundColor: vehicleFilter === v.id || selectedVehicleId === v.id ? v.color : undefined
              }}
            >
              <span>V0{v.id}</span>
            </button>
          ))}
        </div>
      )}

      {/*
        react-leaflet's MapContainer does not reactively re-apply its own
        className after the Leaflet instance mounts (Leaflet's own JS owns
        that DOM node's class list from then on), so the GIS/Graph toggle
        class has to live on this wrapper div instead, targeted via a
        descendant selector in index.css.
      */}
      <div className={`w-full h-full ${mapView === 'graph' ? 'graph-view-grid' : ''}`}>
      <MapContainer
        center={center}
        zoom={12}
        scrollWheelZoom={!compact}
        className="w-full h-full"
      >
        {mapView === 'gis' && (
          // Standard OSM raster tiles at full brightness - a dark CSS
          // filter and CartoDB's dark basemap were both tried; the filter
          // looked vague/washed out and CartoDB's now requires an API key
          // (renders an "API KEY REQUIRED" watermark without one).
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
        )}

        {/* Base Network Edges */}
        {edgeLines.map(e => (
          <Polyline
            key={e.id}
            positions={e.positions}
            pathOptions={{
              color: e.color,
              weight: e.weight,
              opacity: e.opacity,
              className: e.isIncident ? 'incident-road-pulse' : ''
            }}
          >
            <Popup>
              <div className="text-xs space-y-1 font-mono">
                <p className="font-bold text-[#5D7A9E]">{e.roadName}</p>
                {e.highway && (
                  <p className="text-gray-500 text-[10px]">
                    OSM {e.highway}
                    {e.osmWayId ? ` · way ${e.osmWayId}` : ''}
                    {e.speedKph ? ` · ${e.speedKph} km/h (${e.speedSource})` : ''}
                  </p>
                )}
                <p>Free-flow Time: {e.baseTime} min</p>
                <p>Current Time: <span style={{ color: e.color }} className="font-bold">{e.currentTime} min ({e.trafficFactor}×)</span></p>
                {/* State, not a client-side threshold: the backend classified
                    this edge as it wrote the cost. */}
                <p>
                  Sim. traffic state: <span style={{ color: e.color }}>{e.congestionLabel}</span>
                  {e.isIncident ? ' · ⚠ incident on this road' : ''}
                </p>
                {(e.trafficMultiplier != null) && (
                  <p className="text-gray-500 text-[10px]">
                    traffic ×{e.trafficMultiplier} · weather ×{e.weatherMultiplier} · incident ×{e.incidentMultiplier}
                  </p>
                )}
                {onDisruptEdge && (
                  <div className="border-t border-[#3A342E] mt-1.5 pt-1.5 space-y-1">
                    <p className="text-gray-400 text-[10px] uppercase">
                      {e.isIncident ? 'Road Closed' : 'Disrupt This Road'}
                    </p>
                    <div className="flex gap-1">
                      {[
                        { label: 'Low', factor: 1.5, variant: 'success' },
                        { label: 'Medium', factor: 2.5, variant: 'warning' },
                        { label: 'Severe', factor: 4.0, variant: 'destructive' }
                      ].map(sev => (
                        <Button
                          key={sev.label}
                          variant={sev.variant}
                          size="sm"
                          fullWidth={false}
                          disabled={disruptDisabled}
                          onClick={() => onDisruptEdge(e.source, e.destination, sev.factor)}
                        >
                          {sev.label}
                        </Button>
                      ))}
                      {e.isIncident && (
                        <button
                          disabled={disruptDisabled}
                          onClick={() => onDisruptEdge(e.source, e.destination, 1.0)}
                          className="px-1.5 py-0.5 rounded bg-[#1E2A1E]/80 hover:bg-[#1E2A1E] text-[#9ABF87] text-[10px] font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          Reopen
                        </button>
                      )}
                    </div>
                    {disruptDisabled && (
                      <p className="text-[9px] text-gray-500">Optimize the fleet first to enable disruption.</p>
                    )}
                  </div>
                )}
              </div>
            </Popup>
          </Polyline>
        ))}

        {/* Previous Route Overlay - fades out as the new route fades in by
            default ('both'); the operator's explicit before/after pick
            overrides that automatic transition. Same coordinates always. */}
        {previousRouteLines.map((pr, idx) => (
          <Polyline
            key={`prev-route-${idx}`}
            positions={pr.coords}
            pathOptions={{
              color: '#6B6259',
              weight: 2.5,
              dashArray: '6, 8',
              opacity:
                beforeAfterMode === 'after' ? 0 :
                beforeAfterMode === 'before' ? 0.9 :
                beforeAfterMode === 'overlay' ? 0.4 :
                0.4 * (1 - routeTransition)
            }}
          />
        ))}

        {/* Active Optimized Vehicle Routes */}
        {activeRouteLines.map(ar => {
          if (ar.isFilteredOut) return null;

          const baseOpacity = ar.isSelected ? 1.0 : 0.85;
          const activeOpacity =
            beforeAfterMode === 'before' ? 0 :
            beforeAfterMode === 'after' ? baseOpacity :
            beforeAfterMode === 'overlay' ? baseOpacity * 0.6 :
            baseOpacity * Math.max(0.15, routeTransition);

          return (
            <Polyline
              key={`active-route-${ar.vehicleId}`}
              positions={ar.coords}
              eventHandlers={{
                click: () => {
                  const vehicleObj = vehicles.find(v => v.id === ar.vehicleId);
                  if (onSelectVehicle && vehicleObj) onSelectVehicle(vehicleObj, ar.routeObj);
                }
              }}
              pathOptions={{
                color: ar.color,
                weight: ar.isSelected ? 7 : 5,
                opacity: activeOpacity,
                className: `route-glow-v${ar.vehicleId}`
              }}
            >
              <Popup>
                <div className="text-xs space-y-1 font-mono">
                  <p className="font-bold text-sm" style={{ color: ar.color }}>Vehicle 0{ar.vehicleId}</p>
                  <p>Stops: {ar.jobsCount} Jobs</p>
                  <p>Distance: {ar.dist} km</p>
                  <p>Travel Time: {ar.time} min</p>
                  <p className="text-gray-500 text-[10px]">
                    Drawn from: {ar.geometrySource === 'openstreetmap'
                      ? 'OSM road geometry'
                      : ar.geometrySource === 'mixed'
                      ? 'OSM road geometry (partial)'
                      : 'node-to-node links'}
                  </p>
                </div>
              </Popup>
            </Polyline>
          );
        })}

        {/* Nodes (Depot, Jobs, Intersections). In placement mode every node
            is a click target for the operator's manual depot/stop picks,
            rendered from the in-progress draft rather than the committed
            scenario - nothing here is applied until confirmed. */}
        {nodes.map(n => {
          if (placementMode) {
            const isDraftDepot = n.id === draftDepotId;
            const draftStopIndex = draftStopIds.indexOf(n.id);
            const isDraftStop = draftStopIndex !== -1;
            const clickHandlers = { eventHandlers: { click: () => onPlaceNode?.(n.id) } };

            if (isDraftDepot) {
              return (
                <Marker
                  key={`node-${n.id}`}
                  position={[n.lat, n.lng]}
                  icon={createDraftDepotMarkerIcon()}
                  {...clickHandlers}
                />
              );
            }
            if (isDraftStop) {
              return (
                <Marker
                  key={`node-${n.id}`}
                  position={[n.lat, n.lng]}
                  icon={createDraftStopMarkerIcon(draftStopIndex + 1)}
                  {...clickHandlers}
                />
              );
            }
            return (
              <CircleMarker
                key={`node-${n.id}`}
                center={[n.lat, n.lng]}
                radius={5}
                pathOptions={{
                  color: '#C6602E',
                  fillColor: '#3A342E',
                  fillOpacity: 1,
                  weight: 1.5
                }}
                {...clickHandlers}
              />
            );
          }

          const isJob = jobNodeIds.has(n.id);
          const jobObj = jobMap.get(n.id);

          if (n.is_depot) {
            return (
              <Marker
                key={`node-${n.id}`}
                position={[n.lat, n.lng]}
                icon={createDepotMarkerIcon()}
              >
                <Popup>
                  <div className="text-xs font-mono">
                    <p className="font-bold text-[#C1443B] text-sm">CENTRAL DEPOT</p>
                    <p>Node ID: #{n.id}</p>
                  </div>
                </Popup>
              </Marker>
            );
          }

          if (isJob) {
            return (
              <Marker
                key={`node-${n.id}`}
                position={[n.lat, n.lng]}
                icon={createJobMarkerIcon(jobObj.id)}
              >
                <Popup>
                  <div className="text-xs font-mono space-y-1">
                    <p className="font-bold text-[#5D7A9E]">Delivery Job #{jobObj.id}</p>
                    <p>Node: #{n.id}</p>
                    <p>Demand: {jobObj.demand} units</p>
                    <p>Service Time: {jobObj.service_time} min</p>
                  </div>
                </Popup>
              </Marker>
            );
          }

          return (
            <CircleMarker
              key={`node-${n.id}`}
              center={[n.lat, n.lng]}
              radius={3}
              pathOptions={{
                color: '#4A423A',
                fillColor: '#242019',
                fillOpacity: 1,
                weight: 1
              }}
            />
          );
        })}

        {/* Vehicle Markers */}
        {vehicleMarkers.map(vm => (
          <Marker
            key={`vehicle-marker-${vm.vehicleId}`}
            position={vm.position}
            icon={createVehicleMarkerIcon(vm.vehicleId, vm.color, vm.isSelected)}
            eventHandlers={{
              click: () => {
                if (onSelectVehicle && vm.vehicleObj) onSelectVehicle(vm.vehicleObj, vm.routeObj);
              }
            }}
          >
            <Popup>
              <div className="text-xs font-mono">
                <p className="font-bold text-sm" style={{ color: vm.color }}>Vehicle 0{vm.vehicleId}</p>
                <p>Stops: {vm.jobsCount} Jobs</p>
                <p>Distance: {vm.dist} km</p>
                <p>Travel Time: {vm.time} min</p>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      </div>

      {/* Closed Roads panel - lets an operator reopen a road without having
          to re-find it on the map. Only rendered when something is actually
          closed; list and reopen both drive the same onDisruptEdge(...,1.0)
          path the map's own popup uses, so there is no second code path for
          clearing an incident. */}
      {closedEdges.length > 0 && onDisruptEdge && (
        <div className="absolute bottom-3 right-3 z-[1000] clean-panel px-3 py-2 rounded-lg text-xs space-y-1.5 border border-[#332E29] shadow-xl pointer-events-auto max-h-[45vh] max-w-[calc(100vw-2rem)] sm:max-w-xs overflow-y-auto font-mono">
          <div className="flex items-center gap-1.5 text-gray-300 font-semibold uppercase tracking-wider text-[10px]">
            <span className="text-[#E8918A]">⚠</span>
            Closed Roads ({closedEdges.length})
          </div>
          <div className="space-y-1">
            {closedEdges.map(e => (
              <div key={e.id} className="flex items-center justify-between gap-2">
                <span className="text-gray-400 text-[10px] truncate" title={e.roadName || `Node ${e.source} → ${e.destination}`}>
                  {e.roadName || `#${e.source} → #${e.destination}`}
                </span>
                <button
                  disabled={disruptDisabled}
                  onClick={() => onDisruptEdge(e.source, e.destination, 1.0)}
                  className="px-1.5 py-0.5 rounded bg-[#1E2A1E]/80 hover:bg-[#1E2A1E] text-[#9ABF87] text-[10px] font-semibold disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
                >
                  Reopen
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {!compact && (<>
      {/* Mobile Floating Legend Toggle Button */}
      <button
        onClick={() => setIsLegendOpen(!isLegendOpen)}
        className="sm:hidden absolute bottom-3 left-3 z-[1000] clean-panel px-2.5 py-1.5 rounded-lg text-[11px] font-mono font-semibold text-gray-200 border border-[#332E29] shadow-xl pointer-events-auto flex items-center gap-1.5 bg-[#1E1B18]/90 hover:bg-[#26221D] active:scale-95 transition-all"
        aria-label="Toggle Map Legend"
      >
        <span className="text-[#C6602E]">ℹ</span>
        <span>Legend</span>
        <span className="text-[9px] text-gray-400 font-normal">{isLegendOpen ? '▼' : '▲'}</span>
      </button>

      {/* Map Legend Overlay */}
      <div className={`absolute bottom-3 left-3 z-[1000] clean-panel px-3 py-2 rounded-lg text-xs space-y-1.5 border border-[#332E29] shadow-xl pointer-events-auto max-h-[45vh] max-w-[calc(100vw-2rem)] sm:max-w-xs overflow-y-auto ${
        isLegendOpen ? 'block' : 'hidden sm:block'
      }`}>
        <div className="flex items-center justify-between font-semibold text-gray-400 text-[10px] uppercase tracking-wider mb-1">
          <span>MAP LEGEND</span>
          <button
            onClick={() => setIsLegendOpen(false)}
            className="sm:hidden text-gray-400 hover:text-white px-1 font-bold text-xs"
            aria-label="Close Legend"
          >
            ✕
          </button>
        </div>
        {/* What the lines on this map actually are. Stated so an OSM run and
            a synthetic run are never mistaken for each other. */}
        <div className="text-[10px] font-mono text-gray-400 pb-1 border-b border-[#332E29]/60">
          {isOsmNetwork
            ? 'Roads: real OpenStreetMap geometry'
            : 'Roads: synthetic network (straight-line links)'}
        </div>
        <div className="flex items-center space-x-2 text-[11px] font-mono">
          <span className="w-2.5 h-2.5 rounded-full bg-[#C1443B] inline-block"></span>
          <span className="text-gray-300">Depot</span>
        </div>
        <div className="flex items-center space-x-2 text-[11px] font-mono">
          <span className="w-2.5 h-2.5 rounded-full bg-[#5D7A9E] inline-block"></span>
          <span className="text-gray-300">Job Target</span>
        </div>
        {/* Congestion bands, named and coloured exactly as the backend
            classified them. Simulated, and labelled as such - this is a
            traffic model, never a live feed. */}
        <div className="pt-1 border-t border-[#332E29]/60 mt-1">
          <div className="text-[9px] uppercase tracking-wider text-gray-500 mb-1">
            Simulated Traffic (model)
          </div>
          <div className="flex flex-wrap gap-x-2 gap-y-1">
            {CONGESTION_ORDER.map(level => (
              <span key={level} className="flex items-center space-x-1 text-[10px] font-mono">
                <span
                  className="w-3 h-1 rounded inline-block"
                  style={{ backgroundColor: CONGESTION_STYLES[level].color }}
                />
                <span className="text-gray-300">{CONGESTION_STYLES[level].label}</span>
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center space-x-2 text-[11px] font-mono">
          <span className="w-4 h-1 bg-[#C1443B] rounded inline-block animate-pulse"></span>
          <span className="text-gray-300">⚠ Incident Road (operator-injected)</span>
        </div>
        {vehicles.length > 0 && (
          <div className="flex items-center space-x-2 text-[11px] font-mono">
            <span className="flex -space-x-0.5">
              {vehicles.slice(0, 3).map(v => (
                <span
                  key={v.id}
                  className="w-2.5 h-1 rounded-full inline-block ring-1 ring-[#1E1B18]"
                  style={{ backgroundColor: v.color }}
                />
              ))}
            </span>
            <span className="text-gray-300">Vehicle Route (color = vehicle)</span>
          </div>
        )}
        {previousResult && (
          <div className="flex items-center space-x-2 border-t border-[#332E29] pt-1 mt-1 text-[10px] font-mono text-gray-400">
            <span className="w-4 border-t-2 border-dashed border-[#6B6259] inline-block"></span>
            <span>Pre-incident Route (before this re-optimization)</span>
          </div>
        )}
      </div>
      </>)}
    </div>
  );
}
